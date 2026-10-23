"""Upstox adapter (plain REST). Docs: https://upstox.com/developer/api-documentation

Env: UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_REDIRECT_URI (must match the app exactly).
Orders/cancels must come from the static IP registered on the Upstox app (SEBI/NSE rule, 1 Apr 2026).
Token is valid until 03:30 IST next day. Funds and order APIs are down 00:00-05:30 IST.
Smoke test (read-only): python -m brokers.upstox
"""
import gzip
import json
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests

from brokers import IST, Candle, Option, cached_token, tick

API = "https://api.upstox.com"
HFT = "https://api-hft.upstox.com"  # order place/modify/cancel host
MASTER = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
KEYS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "INDIAVIX": "NSE_INDEX|India VIX",
}
DONE = {"complete": "COMPLETE", "rejected": "REJECTED", "cancelled": "CANCELLED",
        "cancelled after market order": "CANCELLED"}  # every other Upstox status is still OPEN


def _login() -> str:
    key, secret, redirect = (os.environ[k] for k in ("UPSTOX_API_KEY", "UPSTOX_API_SECRET", "UPSTOX_REDIRECT_URI"))
    q = urlencode({"response_type": "code", "client_id": key, "redirect_uri": redirect})
    print(f"Log in to Upstox here:\n{API}/v2/login/authorization/dialog?{q}")
    got = input("Paste the redirected URL (or just the code): ").strip()
    code = parse_qs(urlparse(got).query).get("code", [got])[0]
    r = requests.post(f"{API}/v2/login/authorization/token", headers={"Accept": "application/json"}, timeout=15,
                      data={"code": code, "client_id": key, "client_secret": secret,
                            "redirect_uri": redirect, "grant_type": "authorization_code"})
    if r.status_code != 200 or "access_token" not in r.json():
        raise RuntimeError(f"Upstox login failed {r.status_code}: {r.text[:500]}")
    return r.json()["access_token"]


class Broker:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json",
                               "Authorization": "Bearer " + cached_token("upstox", _login)})
        self._fo = (None, [])  # (IST date, NSE_FO option rows of the instrument master)

    def _req(self, method, path, host=API, **kw):
        r = self.s.request(method, host + path, timeout=15, allow_redirects=False, **kw)
        if r.status_code != 200 or r.json().get("status") != "success":
            raise RuntimeError(f"Upstox {method} {path} -> {r.status_code}: {r.text[:500]}")
        return r.json()["data"]

    def funds(self) -> float:
        d = self._req("GET", "/v3/user/get-funds-and-margin", headers={"Api-Version": "3.0"})
        return float(d["available_to_trade"]["cash_available_to_trade"]["total"])  # cash only, no pledge

    def candles(self, index, days) -> list[Candle]:
        k, now = quote(KEYS[index], safe=""), datetime.now(IST)
        start, end, rows = now.date() - timedelta(days - 1), now.date() - timedelta(1), []
        while start <= end:  # historical = past days only, max 1 month per call for 5-min
            stop = min(start + timedelta(27), end)
            rows += self._req("GET", f"/v3/historical-candle/{k}/minutes/5/{stop}/{start}")["candles"]
            start = stop + timedelta(1)
        rows += self._req("GET", f"/v3/historical-candle/intraday/{k}/minutes/5")["candles"]  # today
        out = {}  # keyed by start time: dedupes, then sorted oldest first
        for ts, o, h, l, c, v, *_ in rows:  # the last intraday 5-min bar may still be forming
            t = datetime.fromisoformat(ts).astimezone(IST)
            out[t] = (t, float(o), float(h), float(l), float(c), float(v or 0))
        return [out[t] for t in sorted(out)]

    def ltp(self, keys) -> dict:
        want = {k: KEYS.get(k, k) for k in keys}
        data = self._req("GET", "/v3/market-quote/ltp", params={"instrument_key": ",".join(want.values())})
        # response keys look like "NSE_FO:NIFTY..." / "NSE_INDEX:Nifty 50"; map back via instrument_token
        px = {d["instrument_token"]: float(d["last_price"]) for d in data.values()}
        return {k: px[u] for k, u in want.items()}

    def options(self, index) -> list[Option]:
        today = datetime.now(IST).date()
        if self._fo[0] != today:
            r = requests.get(MASTER, timeout=120)
            r.raise_for_status()
            raw = gzip.decompress(r.content) if r.content[:2] == b"\x1f\x8b" else r.content
            self._fo = (today, [i for i in json.loads(raw)
                                if i.get("segment") == "NSE_FO" and i.get("instrument_type") in ("CE", "PE")])
        return [Option(i["instrument_key"], i["trading_symbol"], index,
                       datetime.fromtimestamp(i["expiry"] / 1000, IST).date(),
                       float(i["strike_price"]), i["instrument_type"], int(i["lot_size"]))
                for i in self._fo[1] if i.get("underlying_key") == KEYS[index]]

    def place(self, opt, side, qty, price, trigger=None) -> str:
        if side not in ("BUY", "SELL") or qty <= 0 or qty % opt.lot:
            raise ValueError(f"bad order: {side} {qty} (lot {opt.lot})")
        body = {"instrument_token": opt.key, "transaction_type": side, "quantity": int(qty),
                "product": "I", "validity": "DAY", "price": tick(price), "disclosed_quantity": 0,
                "order_type": "LIMIT" if trigger is None else "SL",
                "trigger_price": 0 if trigger is None else tick(trigger), "slice": False}
        return self._req("POST", "/v3/order/place", HFT, json=body)["order_ids"][0]

    def order(self, order_id) -> dict:
        d = self._req("GET", "/v2/order/details", params={"order_id": order_id})
        return {"status": DONE.get(d["status"], "OPEN"), "filled": int(d.get("filled_quantity") or 0),
                "avg": float(d.get("average_price") or 0), "msg": d.get("status_message") or d["status"]}

    def cancel(self, order_id) -> None:
        self._req("DELETE", "/v3/order/cancel", HFT, params={"order_id": order_id})


if __name__ == "__main__":  # READ-ONLY smoke test, never places orders
    try:
        import config  # noqa: F401  (loads .env)
    except ImportError:
        pass
    b = Broker()
    print("funds", b.funds())
    q = b.ltp(["NIFTY", "INDIAVIX"])
    print("ltp", q)
    for c in b.candles("NIFTY", 7)[-3:]:
        print("candle", c)
    opts = [o for o in b.options("NIFTY") if o.expiry >= datetime.now(IST).date()]
    exp = min(o.expiry for o in opts)
    ce = min((o for o in opts if o.expiry == exp and o.kind == "CE"), key=lambda o: abs(o.strike - q["NIFTY"]))
    print("ATM CE", ce, b.ltp([ce.key]))
