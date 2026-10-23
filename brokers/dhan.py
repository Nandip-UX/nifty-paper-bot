"""Dhan (DhanHQ v2) adapter, plain REST. Docs: https://dhanhq.co/docs/v2/

Env: DHAN_CLIENT_ID (required). DHAN_ACCESS_TOKEN is optional: tokens live 24 h, so if it is
unset the first call of the day prompts once (paste a token from web.dhan.co, or type a TOTP +
PIN) and caches it via cached_token(). Order APIs only work from your whitelisted static IP.
Smoke test (read-only): python -m brokers.dhan
"""
import csv
import io
import os
import time
from datetime import date, datetime, timedelta
from getpass import getpass

import requests

from brokers import IST, Option, cached_token, tick

API = "https://api.dhan.co/v2"
SCRIP_MASTER = "https://images.dhan.co/api-data/api-scrip-master.csv"  # compact CSV
INDEX_IDS = {"NIFTY": "13", "BANKNIFTY": "25", "FINNIFTY": "27", "INDIAVIX": "21"}  # IDX_I
STATUS = {"TRADED": "COMPLETE", "CANCELLED": "CANCELLED", "REJECTED": "REJECTED", "EXPIRED": "CANCELLED"}


class Broker:
    def __init__(self):
        self.cid = os.environ["DHAN_CLIENT_ID"]
        token = os.environ.get("DHAN_ACCESS_TOKEN") or cached_token("dhan", self._login)
        self.http = requests.Session()
        self.http.headers.update({"access-token": token, "client-id": self.cid, "Accept": "application/json"})
        self._quote_at = 0.0  # Market Quote API allows 1 request/second
        self._opts, self._opts_day = {}, None

    def _login(self) -> str:
        s = input("Dhan: paste today's access token (web.dhan.co > Access DhanHQ APIs) or your TOTP: ").strip()
        if s.isdigit():  # TOTP -> token via /app/generateAccessToken (needs TOTP enabled on the account)
            params = {"dhanClientId": self.cid, "pin": getpass("Dhan PIN: "), "totp": s}
            r = requests.post("https://auth.dhan.co/app/generateAccessToken", params=params, timeout=15)
            if not r.ok or "accessToken" not in r.json():
                raise RuntimeError(f"Dhan login failed: {r.status_code} {r.text[:300]}")
            s = r.json()["accessToken"]
        r = requests.get(API + "/profile", headers={"access-token": s}, timeout=15)  # validate before caching
        if not r.ok:
            raise RuntimeError(f"Dhan token rejected: {r.status_code} {r.text[:300]}")
        return s

    def _req(self, method, path, **kw):
        r = self.http.request(method, API + path, timeout=15, **kw)
        if not r.ok:
            raise RuntimeError(f"Dhan {method} {path}: HTTP {r.status_code} {r.text[:300]}")
        body = r.json() if r.content else {}
        if isinstance(body, dict) and body.get("status") == "failed":  # Data APIs report errors this way
            raise RuntimeError(f"Dhan {method} {path}: {body}")
        return body

    def funds(self) -> float:
        d = self._req("GET", "/fundlimit")
        bal = d["availabelBalance"] if "availabelBalance" in d else d["availableBalance"]  # Dhan's spelling
        return max(0.0, float(bal) - float(d.get("collateralAmount") or 0))  # cash only, no pledge margin

    def candles(self, index, days):
        now = datetime.now(IST)
        start = now.date() - timedelta(days=days - 1)
        out, frm = {}, start
        while frm <= now.date():  # intraday charts serve at most 90 days per call
            to = min(frm + timedelta(days=85), now.date())
            body = {"securityId": INDEX_IDS[index], "exchangeSegment": "IDX_I", "instrument": "INDEX", "interval": 5,
                    "fromDate": f"{frm} 00:00:00",
                    "toDate": now.strftime("%Y-%m-%d %H:%M:%S") if to == now.date() else f"{to} 23:59:59"}
            d = self._req("POST", "/charts/intraday", json=body)
            for t, o, h, l, c, v in zip(d["timestamp"], d["open"], d["high"], d["low"], d["close"], d["volume"]):
                ts = datetime.fromtimestamp(t, IST)  # Unix epoch seconds of the candle start
                out[ts] = (ts, float(o), float(h), float(l), float(c), float(v))
            frm = to + timedelta(days=1)
        return sorted(x for x in out.values() if x[0].date() >= start)

    def ltp(self, keys):
        ids = {k: ("IDX_I", INDEX_IDS[k]) if k in INDEX_IDS else tuple(k.split(":")) for k in keys}
        body = {}
        for seg, sid in ids.values():
            body.setdefault(seg, []).append(int(sid))
        time.sleep(max(0.0, self._quote_at + 1.05 - time.monotonic()))
        self._quote_at = time.monotonic()
        data = self._req("POST", "/marketfeed/ltp", json=body)["data"]
        return {k: float(data[seg][sid]["last_price"]) for k, (seg, sid) in ids.items()}

    def options(self, index):
        today = datetime.now(IST).date()
        if self._opts_day != today:
            r = requests.get(SCRIP_MASTER, timeout=120)
            r.raise_for_status()
            opts = {}
            for row in csv.DictReader(io.StringIO(r.content.decode())):
                if row["SEM_EXM_EXCH_ID"] != "NSE" or row["SEM_INSTRUMENT_NAME"] != "OPTIDX":
                    continue
                name = row["SEM_TRADING_SYMBOL"].split("-")[0]  # e.g. NIFTY-Mar2026-25000-CE
                opts.setdefault(name, []).append(Option(
                    key=f"NSE_FNO:{row['SEM_SMST_SECURITY_ID']}", symbol=row["SEM_CUSTOM_SYMBOL"], index=name,
                    expiry=date.fromisoformat(row["SEM_EXPIRY_DATE"][:10]), strike=float(row["SEM_STRIKE_PRICE"]),
                    kind=row["SEM_OPTION_TYPE"], lot=int(float(row["SEM_LOT_UNITS"]))))
            self._opts, self._opts_day = opts, today
        return self._opts[index]

    def place(self, opt, side, qty, price, trigger=None):
        if side not in ("BUY", "SELL") or qty <= 0 or qty % opt.lot:
            raise ValueError(f"bad order: {side} {qty} (lot {opt.lot})")
        seg, sid = opt.key.split(":")
        body = {"dhanClientId": self.cid, "transactionType": side, "exchangeSegment": seg, "productType": "INTRADAY",
                "orderType": "LIMIT" if trigger is None else "STOP_LOSS", "validity": "DAY", "securityId": sid,
                "quantity": int(qty), "disclosedQuantity": 0, "price": tick(price),
                "triggerPrice": 0.0 if trigger is None else tick(trigger), "afterMarketOrder": False}
        return str(self._req("POST", "/orders", json=body)["orderId"])

    def order(self, order_id):
        d = self._req("GET", f"/orders/{order_id}")
        d = d[0] if isinstance(d, list) else d  # documented as an object; tolerate a 1-item list
        st = d["orderStatus"]  # TRANSIT/PENDING/PART_TRADED/TRIGGERED -> OPEN
        return {"status": STATUS.get(st, "OPEN"), "filled": int(d.get("filledQty") or 0),
                "avg": float(d.get("averageTradedPrice") or 0), "msg": d.get("omsErrorDescription") or st}

    def cancel(self, order_id):
        self._req("DELETE", f"/orders/{order_id}")


if __name__ == "__main__":  # READ-ONLY smoke test: never places orders
    try:
        import config  # noqa: F401  (loads .env)
    except ImportError:
        pass
    b = Broker()
    print("funds:", b.funds())
    q = b.ltp(["NIFTY", "INDIAVIX"])
    print("ltp:", q)
    for c in b.candles("NIFTY", 3)[-3:]:
        print("candle:", c)
    opts = b.options("NIFTY")
    expiry = min(o.expiry for o in opts if o.expiry >= datetime.now(IST).date())
    atm = min((o for o in opts if o.expiry == expiry and o.kind == "CE"), key=lambda o: abs(o.strike - q["NIFTY"]))
    print("ATM CE:", atm, b.ltp([atm.key]))
