"""Free data source for PAPER trading with no broker account: live NIFTY and India VIX from Yahoo
Finance; NIFTY option prices are modelled with Black-Scholes at India VIX (real option quotes need a
broker). Use BROKER=yahoo in .env, then `python bot.py`. It cannot place real orders.
Smoke test: python -m brokers.yahoo
"""
import os
import time
from datetime import date, datetime, timedelta
from math import erf, exp, log, sqrt

import requests

from brokers import IST, Candle, Option

SYMBOLS = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "INDIAVIX": "^INDIAVIX"}
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
LOT, STEP, RATE = 65, 50, 0.065  # NIFTY lot size (from Jan 2026), strike step, risk-free rate


def _n(x: float) -> float:
    return 0.5 * (1 + erf(x / sqrt(2)))


def premium(spot: float, strike: float, years: float, iv: float, kind: str) -> float:
    """Black-Scholes option price."""
    if years <= 0:
        return max(0.0, spot - strike if kind == "CE" else strike - spot)
    d1 = (log(spot / strike) + (RATE + iv * iv / 2) * years) / (iv * sqrt(years))
    d2 = d1 - iv * sqrt(years)
    if kind == "CE":
        return spot * _n(d1) - strike * exp(-RATE * years) * _n(d2)
    return strike * exp(-RATE * years) * _n(-d2) - spot * _n(-d1)


class Broker:
    def __init__(self):
        self.http = requests.Session()
        self.http.headers["User-Agent"] = "Mozilla/5.0"
        self._px: dict = {}  # symbol -> (fetched at, price); a few seconds of caching keeps Yahoo happy

    def _chart(self, symbol: str, rng: str, interval: str) -> dict:
        r = self.http.get(URL.format(symbol), params={"range": rng, "interval": interval}, timeout=15)
        r.raise_for_status()
        return r.json()["chart"]["result"][0]

    def _last(self, symbol: str, ttl: float) -> float:
        at, px = self._px.get(symbol, (0.0, 0.0))
        if time.monotonic() - at > ttl:
            px = float(self._chart(symbol, "1d", "1m")["meta"]["regularMarketPrice"])
            self._px[symbol] = (time.monotonic(), px)
        return px

    def funds(self) -> float:
        return float(os.getenv("PAPER_CAPITAL") or 150_000)

    def candles(self, index, days) -> list[Candle]:
        res = self._chart(SYMBOLS[index], f"{days}d", "5m")
        q = res["indicators"]["quote"][0]
        out = []
        for ts, o, h, l, c, v in zip(res["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"]):
            t = datetime.fromtimestamp(ts, IST)
            if None in (o, h, l, c) or t.minute % 5 or t.second:  # skip Yahoo's live partial point
                continue
            out.append((t, float(o), float(h), float(l), float(c), float(v or 0)))
        return out

    def options(self, index) -> list[Option]:
        if index != "NIFTY":
            raise ValueError("the yahoo paper source models NIFTY options only")
        today = datetime.now(IST).date()
        tue = today + timedelta(days=(1 - today.weekday()) % 7)  # NIFTY weekly expiry is Tuesday
        atm = round(self._last("^NSEI", 4) / STEP) * STEP  # ponytail: ignores holiday-shifted expiries
        return [Option(f"{e}|{k}|{x}", f"NIFTY{e:%d%b}{k}{x}".upper(), "NIFTY", e, float(k), x, LOT)
                for e in (tue, tue + timedelta(days=7))
                for k in range(atm - 40 * STEP, atm + 41 * STEP, STEP) for x in ("CE", "PE")]

    def ltp(self, keys) -> dict:
        out = {}
        for k in keys:
            if k in SYMBOLS:
                out[k] = self._last(SYMBOLS[k], 4)
                continue
            e, strike, kind = k.split("|")
            expiry = datetime.combine(date.fromisoformat(e), datetime.min.time(), IST).replace(hour=15, minute=30)
            years = (expiry - datetime.now(IST)).total_seconds() / (365 * 86400)
            iv = self._last("^INDIAVIX", 300) / 100
            out[k] = round(premium(self._last("^NSEI", 4), float(strike), years, iv, kind), 2)
        return out

    def place(self, *args, **kwargs):
        raise RuntimeError("yahoo is a data source for paper trading only; it cannot place orders")

    order = cancel = place


if __name__ == "__main__":  # read-only smoke test
    b = Broker()
    px = b.ltp(["NIFTY", "INDIAVIX"])
    print("ltp:", px)
    for c in b.candles("NIFTY", 2)[-3:]:
        print("candle:", c)
    opts = [o for o in b.options("NIFTY") if o.expiry > datetime.now(IST).date() and o.kind == "CE"]
    atm = min(opts, key=lambda o: (o.expiry, abs(o.strike - px["NIFTY"])))
    print("ATM CE:", atm.symbol, "model price:", b.ltp([atm.key])[atm.key])
