"""Zerodha Kite Connect adapter (official `kiteconnect` SDK, checked against v5.2.2).

Env: KITE_API_KEY, KITE_API_SECRET. Login once a day (token dies at 6 AM next day).
Needs the paid Kite Connect plan (LTP + historical data). Orders are accepted only from the
static IP whitelisted at developers.kite.trade (SEBI/NSE rule since 1 Apr 2026).
Read-only smoke test, from the project root:  python -m brokers.zerodha
"""
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from kiteconnect import KiteConnect

from brokers import IST, Candle, Option, cached_token, tick

# Kite instrument master, segment INDICES: (ltp key "NSE:<tradingsymbol>", instrument_token)
INDICES = {
    "NIFTY": ("NSE:NIFTY 50", 256265),
    "BANKNIFTY": ("NSE:NIFTY BANK", 260105),
    "FINNIFTY": ("NSE:NIFTY FIN SERVICE", 257801),
    "INDIAVIX": ("NSE:INDIA VIX", 264969),
}
# End states. Every other Kite status (OPEN, TRIGGER PENDING, OPEN PENDING, VALIDATION PENDING,
# PUT ORDER REQ RECEIVED, MODIFY/CANCEL PENDING, ...) is still live, so it maps to OPEN.
FINAL = ("COMPLETE", "CANCELLED", "REJECTED")
FMT = "%Y-%m-%d %H:%M:%S"  # historical from/to, read by Kite as IST


class Broker:
    def __init__(self):
        self.kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
        secret = os.environ["KITE_API_SECRET"]

        def fetch():
            print("Log in to Zerodha here:\n ", self.kite.login_url())
            s = input("Paste the redirected URL (or just the request_token): ").strip()
            request_token = parse_qs(urlparse(s).query).get("request_token", [s])[0]
            return self.kite.generate_session(request_token, api_secret=secret)["access_token"]

        self.kite.set_access_token(cached_token("zerodha", fetch))
        self._nfo = (None, [])  # (IST date, kite.instruments("NFO")), refreshed once a day

    def funds(self) -> float:
        # live_balance = cash left after today's usage (premiums, margins, M2M). Not `net`: it adds
        # pledged collateral, which cannot pay option premium. Not `cash`: it is the day-start figure.
        return float(self.kite.margins("equity")["available"]["live_balance"])

    def candles(self, index, days) -> list[Candle]:
        now = datetime.now(IST)
        start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        while start < now:  # Kite serves at most 100 days of 5-minute data per call; rows oldest first
            end = min(start + timedelta(days=90), now)
            rows += self.kite.historical_data(INDICES[index][1], start.strftime(FMT), end.strftime(FMT), "5minute")
            start = end + timedelta(seconds=1)
        return [
            (r["date"].astimezone(IST), float(r["open"]), float(r["high"]), float(r["low"]),
             float(r["close"]), float(r["volume"]))
            for r in rows
        ]

    def ltp(self, keys) -> dict:
        ids = {k: INDICES[k][0] if k in INDICES else k for k in keys}
        data = self.kite.ltp(*ids.values())  # a key with no data is absent -> KeyError below
        return {k: float(data[i]["last_price"]) for k, i in ids.items()}

    def options(self, index) -> list[Option]:
        today = datetime.now(IST).date()
        if self._nfo[0] != today:
            self._nfo = (today, self.kite.instruments("NFO"))
        return [
            Option(f"NFO:{r['tradingsymbol']}", r["tradingsymbol"], index, r["expiry"],
                   float(r["strike"]), r["instrument_type"], int(r["lot_size"]))
            for r in self._nfo[1]
            if r["segment"] == "NFO-OPT" and r["name"] == index and r["instrument_type"] in ("CE", "PE")
        ]

    def place(self, opt, side, qty, price, trigger=None) -> str:
        # LIMIT / SL only, so no market_protection (Kite requires it only for MARKET and SL-M).
        return self.kite.place_order(
            variety="regular", exchange="NFO", tradingsymbol=opt.symbol, transaction_type=side,
            quantity=int(qty), product="MIS", order_type="LIMIT" if trigger is None else "SL",
            price=tick(price), trigger_price=None if trigger is None else tick(trigger),
            validity="DAY",
        )

    def order(self, order_id) -> dict:
        o = self.kite.order_history(order_id)[-1]  # history is oldest first
        return {
            "status": o["status"] if o["status"] in FINAL else "OPEN",
            "filled": int(o["filled_quantity"] or 0),
            "avg": float(o["average_price"] or 0),
            "msg": o["status_message"] or "",
        }

    def cancel(self, order_id) -> None:
        self.kite.cancel_order("regular", order_id)


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
