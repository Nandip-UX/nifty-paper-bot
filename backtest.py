"""Replay the live rules (same brain + risk code) on past 5-minute index candles.

    python backtest.py --yahoo              last ~60 days of NIFTY from Yahoo, no broker needed
    python backtest.py --broker zerodha     history from your broker
    python backtest.py candles.csv          CSV: time(ISO, IST),open,high,low,close,volume

Results in index points and R are exact for the rules. Rs figures are estimates: option move =
DELTA x index move, premium ~Rs 200 for costs; theta, IV changes and VIX/research filters are ignored.
"""
import argparse
import csv
import json
import urllib.request
from datetime import datetime

import brain
import config as C
import risk
from brokers import IST

BAR = brain.BAR


def yahoo(symbol: str = "^NSEI") -> list:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=60d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = zip(res["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"])
    return [(datetime.fromtimestamp(ts, IST), o, h, l, c, v or 0) for ts, o, h, l, c, v in rows if None not in (o, h, l, c)]


def from_csv(path: str) -> list:
    with open(path) as f:
        return [(datetime.fromisoformat(r["time"]).astimezone(IST), float(r["open"]), float(r["high"]),
                 float(r["low"]), float(r["close"]), float(r.get("volume") or 0)) for r in csv.DictReader(f)]


def replay(bars: list, lot: int, balance: float, prem: float = 200.0, index: str = "NIFTY") -> list[dict]:
    trades, days = [], sorted({c[0].date() for c in bars})
    for d in days[1:]:
        t, size0, count, streak, pnl = None, 0, 0, 0, 0.0
        for i in (i for i, c in enumerate(bars) if c[0].date() == d):
            ts, _, h, l, c, _ = bars[i]
            end = ts + BAR
            if t:  # manage with this bar's range, stop checked before targets
                ex = brain.check_exit(t, h, l, end)
                if ex:
                    reason, lots = ex
                    px = {"stop loss": t.sl, "breakeven stop": t.sl, "target 1": t.s.t1, "target 2": t.s.t2}.get(reason, c)
                    if reason == "target 1":
                        t.t1_done, t.sl = True, t.s.entry
                    if lots:
                        t.pnl += leg(t, lots, px, lot, prem)
                        t.lots -= lots
            if t and t.lots and brain.fading(t, bars[: i + 1]):
                t.pnl += leg(t, t.lots, c, lot, prem)
                t.lots = 0
            if t and not t.lots:
                pnl += t.pnl
                streak = streak + 1 if t.pnl < 0 else 0
                trades.append({"day": d, "in": t.opened, "side": t.s.side, "pnl": t.pnl,
                               "r": t.pnl / (C.DELTA * abs(t.s.entry - t.s.sl) * lot * size0)})
                t = None
            if t or risk.gate(end, count, streak, pnl, balance, False):
                continue
            hist = bars[: i + 1]
            sides, _ = brain.market(hist, end, 0.0, {})
            s, _ = brain.chart(index, hist, end)
            if not s or s.side not in sides:
                continue
            lots, _ = risk.size(s, prem, lot, balance, balance)
            if lots:
                count += 1
                t, size0 = brain.Trade(s, lots=lots, sl=s.sl, opened=end), lots
    return trades


def leg(t: brain.Trade, lots: int, px: float, lot: int, prem: float) -> float:
    pts = (px - t.s.entry) * (1 if t.s.side == "LONG" else -1)
    qty = lots * lot
    return C.DELTA * pts * qty - C.costs(2 * prem * qty)


def summary(trades: list[dict], days: int) -> str:
    if not trades:
        return f"{days} days, no trades"
    wins = [t for t in trades if t["pnl"] > 0]
    gross_win, gross_loss = sum(t["pnl"] for t in wins), -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    equity = peak = dd = 0.0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    by_day: dict = {}
    for t in trades:
        by_day[t["day"]] = by_day.get(t["day"], 0) + t["pnl"]
    return (f"{days} trading days, {len(trades)} trades ({len(trades) / days:.1f}/day), "
            f"win rate {len(wins) / len(trades):.0%}, avg R {sum(t['r'] for t in trades) / len(trades):+.2f}\n"
            f"net Rs {equity:,.0f} | profit factor {gross_win / gross_loss if gross_loss else float('inf'):.2f} | "
            f"max drawdown Rs {dd:,.0f} | green days {sum(v > 0 for v in by_day.values())}/{len(by_day)} | "
            f"worst day Rs {min(by_day.values()):,.0f} | best day Rs {max(by_day.values()):,.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--yahoo", action="store_true")
    ap.add_argument("--broker")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--lot", type=int, default=65, help="lot size (check the current NIFTY lot)")
    ap.add_argument("--balance", type=float, default=150_000)
    ap.add_argument("-v", action="store_true", help="print every trade")
    a = ap.parse_args()
    if a.broker:
        from brokers import connect  # config (imported above) has loaded .env
        bars = connect(a.broker).candles("NIFTY", a.days)
    else:
        bars = yahoo() if a.yahoo else from_csv(a.csv)
    result = replay(bars, a.lot, a.balance)
    if a.v:
        for t in result:
            print(f"{t['in']:%Y-%m-%d %H:%M} {t['side']:5} R {t['r']:+.2f}  Rs {t['pnl']:,.0f}")
    print(summary(result, len({c[0].date() for c in bars}) - 1))
