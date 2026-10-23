"""Download years of 5-minute NIFTY and India VIX candles from Upstox's public historical API
into data/*.csv for strategy research, plus real 5-minute prices of every currently listed NIFTY
option near the money (expired contracts are not public). Runs on GitHub Actions (data.yml), or
anywhere Upstox is reachable:  python fetch_data.py 2022-01-01"""
import csv
import gzip
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

KEYS = {"nifty": "NSE_INDEX|Nifty 50", "vix": "NSE_INDEX|India VIX"}
start = date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2022-01-01")
Path("data").mkdir(exist_ok=True)
for name, key in KEYS.items():
    rows, d = {}, start
    while d <= date.today():  # minute candles: at most ~1 month per call
        to = min(d + timedelta(days=27), date.today())
        url = f"https://api.upstox.com/v3/historical-candle/{quote(key, safe='')}/minutes/5/{to}/{d}"
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"{name} {d}..{to}: HTTP {r.status_code} {r.text[:300]}")
        for c in r.json()["data"]["candles"]:
            rows[c[0]] = c[:6]
        d = to + timedelta(days=1)
        time.sleep(0.3)
    with open(f"data/{name}_5m.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        w.writerows(rows[k] for k in sorted(rows))
    print(f"{name}: {len(rows)} bars, {min(rows)[:10]} .. {max(rows)[:10]}")

# real option prices: every NIFTY CE/PE expiring within 100 days, strikes (step 100) the index visited
with open("data/nifty_5m.csv") as f:
    recent = [float(r["close"]) for r in csv.DictReader(f) if r["time"] >= str(date.today() - timedelta(days=120))]
lo, hi = min(recent) - 300, max(recent) + 300
master = json.loads(gzip.decompress(requests.get(
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz", timeout=120).content))
picks = [i for i in master if i.get("segment") == "NSE_FO" and i.get("underlying_key") == "NSE_INDEX|Nifty 50"
         and i.get("instrument_type") in ("CE", "PE") and lo <= i["strike_price"] <= hi and i["strike_price"] % 100 == 0
         and i["expiry"] / 1000 <= time.time() + 100 * 86400]
print(f"options: {len(picks)} contracts, strikes {lo:.0f}-{hi:.0f}")
with open("data/nifty_options_5m.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["expiry", "strike", "kind", "time", "open", "high", "low", "close", "volume", "oi"])
    for n, i in enumerate(picks):
        exp = date.fromtimestamp(i["expiry"] / 1000)
        d = date.today() - timedelta(days=120)
        while d <= date.today():
            to = min(d + timedelta(days=27), date.today())
            r = requests.get(f"https://api.upstox.com/v3/historical-candle/{quote(i['instrument_key'], safe='')}"
                             f"/minutes/5/{to}/{d}", headers={"Accept": "application/json"}, timeout=30)
            if r.status_code == 200:
                for c in sorted(r.json()["data"]["candles"]):
                    w.writerow([exp, int(i["strike_price"]), i["instrument_type"], *c[:7]])
            d = to + timedelta(days=1)
            time.sleep(0.25)
        if n % 50 == 0:
            print(f"  {n}/{len(picks)}", flush=True)
