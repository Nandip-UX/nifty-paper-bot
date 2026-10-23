"""Angel One SmartAPI adapter (official `smartapi-python` SDK, checked against v1.5.5 = GitHub HEAD).

Env: ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SECRET. Logs in by itself (PIN + TOTP);
Angel ends every session at midnight. API and data are free. Orders are accepted only from the
static IPv4 registered on the API key (SEBI/NSE rule since 1 Apr 2026); data calls work from anywhere.
pip install smartapi-python pyotp logzero websocket-client   (1.5.5 imports the last two, undeclared)
Read-only smoke test, from the project root:  python -m brokers.angel
"""
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta

import pyotp
import requests
from SmartApi import SmartConnect

from brokers import IST, Candle, Option, tick

# Scrip master rows exch_seg NSE, instrumenttype AMXIDX: symbol token of each index spot
INDICES = {"NIFTY": "99926000", "BANKNIFTY": "99926009", "FINNIFTY": "99926037", "INDIAVIX": "99926017"}
MASTER = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
# End states. Every other Angel status (open, trigger pending, open pending, validation pending,
# modify/cancel pending, ...) is still live, so it maps to OPEN.
FINAL = {"complete": "COMPLETE", "cancelled": "CANCELLED", "rejected": "REJECTED"}
FMT = "%Y-%m-%d %H:%M"  # getCandleData fromdate/todate, read as IST


def ok(r):
    """SmartAPI replies {status, message, errorcode, data}; the SDK returns failures instead of raising."""
    if not isinstance(r, dict) or r.get("status") is not True:
        raise RuntimeError(f"Angel API error: {r}")
    return r["data"]


class Broker:
    def __init__(self):
        self.api = SmartConnect(api_key=os.environ["ANGEL_API_KEY"], timeout=10)
        # The SDK logs request params (your PIN, on a failed login) and auth headers to
        # stderr and ./logs/<date>/app.log; silence it. Errors still raise with Angel's message.
        logging.getLogger("logzero_default").disabled = True
        try:  # the SDK sends a hard-coded X-ClientPublicIP; send the real (static) one
            self.api.clientPublicIp = requests.get("https://api.ipify.org", timeout=5).text.strip()
        except requests.RequestException:
            pass
        totp = pyotp.TOTP(os.environ["ANGEL_TOTP_SECRET"]).now()
        ok(self.api.generateSession(os.environ["ANGEL_CLIENT_CODE"], os.environ["ANGEL_PIN"], totp))
        self._nfo = (None, [])  # (IST date, NFO OPTIDX rows of the scrip master), refreshed once a day
        self._quoted = 0.0  # time of the last quote call

    def funds(self) -> float:
        # Angel's docs do not define the getRMS fields. `net` is the overall margin left; users report
        # `availablecash` can include pledge margin, which cannot pay option premium. Take the
        # smaller of the two, so buying power is never overstated.
        r = ok(self.api.rmsLimit())
        return min(float(r["net"]), float(r["availablecash"]))

    def candles(self, index, days) -> list[Candle]:
        now = datetime.now(IST)
        start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        while start < now:  # FIVE_MINUTE serves at most 100 days per call; rows come oldest first
            end = min(start + timedelta(days=90), now)
            rows += ok(self.api.getCandleData({
                "exchange": "NSE", "symboltoken": INDICES[index], "interval": "FIVE_MINUTE",
                "fromdate": start.strftime(FMT), "todate": end.strftime(FMT),
            })) or []
            start = end + timedelta(minutes=1)
        # row = ["2025-04-02T09:30:00+05:30", open, high, low, close, volume]
        return [(datetime.fromisoformat(r[0]).astimezone(IST), *map(float, r[1:6])) for r in rows]

    def ltp(self, keys) -> dict:
        ids = {k: ("NSE", INDICES[k]) if k in INDICES else tuple(k.split(":")) for k in keys}
        want = {}
        for exchange, token in ids.values():
            want.setdefault(exchange, []).append(token)
        time.sleep(max(0.0, self._quoted + 1 - time.monotonic()))  # quote API: <= 1 call/s, 50 tokens
        self._quoted = time.monotonic()
        got = ok(self.api.getMarketData("LTP", want))["fetched"]
        px = {(q["exchange"], q["symbolToken"]): float(q["ltp"]) for q in got}
        return {k: px[i] for k, i in ids.items()}  # a key Angel did not fetch -> KeyError

    def options(self, index) -> list[Option]:
        today = datetime.now(IST).date()
        if self._nfo[0] != today:  # big file: parse only OPTIDX rows (as fast as json.loads, 1/3 the RAM)
            resp = requests.get(MASTER, timeout=120)
            resp.raise_for_status()
            rows = [json.loads(m) for m in re.findall(rb'\{[^{}]*"OPTIDX"[^{}]*\}', resp.content)]
            self._nfo = (today, [r for r in rows if r["exch_seg"] == "NFO" and r["instrumenttype"] == "OPTIDX"])
        return [  # e.g. symbol NIFTY27OCT2625000CE, expiry 27OCT2026, strike "2500000.000000" (x100)
            Option(f"NFO:{r['token']}", r["symbol"], index, datetime.strptime(r["expiry"], "%d%b%Y").date(),
                   float(r["strike"]) / 100, r["symbol"][-2:], int(r["lotsize"]))
            for r in self._nfo[1]
            if r["name"] == index
        ]

    def place(self, opt, side, qty, price, trigger=None) -> str:
        # LIMIT / stop-loss-limit only: SEBI's API rules bar MARKET and IOC orders.
        variety = "NORMAL" if trigger is None else "STOPLOSS"
        tag = uuid.uuid4().hex[:16]  # ordertag (< 20 chars) finds the order if the reply is lost
        p = {
            "variety": variety, "tradingsymbol": opt.symbol, "symboltoken": opt.key.split(":")[1],
            "transactiontype": side, "exchange": "NFO", "producttype": "INTRADAY", "duration": "DAY",
            "ordertype": "LIMIT" if trigger is None else "STOPLOSS_LIMIT", "quantity": str(int(qty)),
            "price": str(tick(price)), "triggerprice": None if trigger is None else str(tick(trigger)),
            "ordertag": tag,
        }
        try:  # placeOrder() would swallow the error message, so use the full-response variant
            d = ok(self.api.placeOrderFullResponse(p))
        except Exception:  # timeout or garbled reply: the order may still have reached Angel
            time.sleep(1)  # order book allows 1 call/s
            d = next((o for o in ok(self.api.orderBook()) or [] if o.get("ordertag") == tag), None)
            if d is None:
                raise
        # cancel needs the variety, the status call needs uniqueorderid
        return f"{variety}:{d['orderid']}:{d['uniqueorderid']}"

    def order(self, order_id) -> dict:
        # Individual order status (10 calls/s) instead of the whole order book (1 call/s). Called
        # directly: the SDK's individual_order_details() has no timeout and hides errors.
        url = self.api.root + SmartConnect._routes["api.individual.order.details"] + order_id.split(":")[2]
        headers = self.api.requestHeaders() | {"Authorization": f"Bearer {self.api.access_token}"}
        o = ok(requests.get(url, headers=headers, timeout=10).json())
        return {
            "status": FINAL.get(str(o["status"]).lower(), "OPEN"),
            "filled": int(o["filledshares"] or 0),
            "avg": float(o["averageprice"] or 0),
            "msg": o["text"] or "",
        }

    def cancel(self, order_id) -> None:
        variety, orderid, _ = order_id.split(":")
        ok(self.api.cancelOrder(orderid, variety))


if __name__ == "__main__":  # READ-ONLY smoke test: never places an order
    try:
        import config  # noqa: F401  (loads .env)
    except ImportError:
        pass
    b = Broker()
    print("funds:", b.funds())
    px = b.ltp(["NIFTY", "INDIAVIX"])
    print("ltp:", px)
    for c in b.candles("NIFTY", 5)[-3:]:
        print("candle:", c)
    ces = [o for o in b.options("NIFTY") if o.kind == "CE" and o.expiry >= datetime.now(IST).date()]
    expiry = min(o.expiry for o in ces)
    atm = min((o for o in ces if o.expiry == expiry), key=lambda o: abs(o.strike - px["NIFTY"]))
    print("ATM CE:", atm, "ltp:", b.ltp([atm.key])[atm.key])
