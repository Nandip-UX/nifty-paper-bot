"""Download years of 5-minute NIFTY and India VIX candles from Upstox's public historical API
into data/*.csv for strategy research. Runs on GitHub Actions (data.yml), or anywhere Upstox
is reachable:  python fetch_data.py 2022-01-01"""
import csv
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
