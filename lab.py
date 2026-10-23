"""Strategy lab: tests strategy families on years of 5-min NIFTY + India VIX (data/ from fetch_data.py).

    python lab.py buy     the real bot (breakout option buying) + variants, every day since 2022
    python lab.py sell    09:20 short straddle / iron fly family, chosen on 2022-23, judged on 2024-26
    python lab.py real    real option prices (data/nifty_options_5m.csv) vs both models, 09:20 -> 15:15

No free history of option prices exists, so options are priced by Black-Scholes at the live India
VIX, with costs and 0.5% slippage per fill. How time decay is counted swings results, so every test
runs under two conventions: "calendar" (decay spread over 24h, 365 days) and "trading" (decay only in
market hours, 252 days). Trust only what makes money under both.
"""
import bisect
import contextlib
import csv
import io
import logging
import sys
import time as _time
from datetime import date, datetime, time, timedelta
from pathlib import Path

import config as C
from brokers import IST, Option
from brokers.yahoo import premium

HERE = Path(__file__).resolve().parent
BAR = timedelta(minutes=5)
LOT, SLIP = 65, 0.005


def load(name: str) -> list:
    with open(HERE / "data" / f"{name}_5m.csv") as f:
        return [(datetime.fromisoformat(r["time"]), float(r["open"]), float(r["high"]), float(r["low"]),
                 float(r["close"])) for r in csv.DictReader(f)]


BARS, VIXB = load("nifty"), load("vix")
STARTS, VSTARTS = [b[0] for b in BARS], [b[0] for b in VIXB]
DAYS = sorted({b[0].date() for b in BARS})


def vix(at: datetime, field: int = 4) -> float:
    """India VIX bar covering `at` (field 4 = close, 2 = high), as a decimal vol."""
    i = max(0, bisect.bisect_right(VSTARTS, at) - 1)
    return VIXB[i][field] / 100


def expiry(d: date) -> date:
    """NIFTY weekly expiry on/after d: Thursday until Aug 2025, Tuesday from Sep 2025 (holidays ignored)."""
    wd = 3 if d < date(2025, 9, 1) else 1
    return d + timedelta(days=(wd - d.weekday()) % 7)


def years(now: datetime, exp: date, mode: str) -> float:
    close = datetime.combine(exp, time(15, 30), IST)
    if mode == "calendar":
        return max(0.0, (close - now).total_seconds()) / (365 * 86400)
    today_left = max(0.0, (datetime.combine(now.date(), time(15, 30), IST) - now).total_seconds() / 60)
    days = sum(1 for k in range(1, (exp - now.date()).days + 1) if (now.date() + timedelta(k)).weekday() < 5)
    return (today_left + 375 * days) / (375 * 252)


def price(spot: float, strike: float, kind: str, at: datetime, exp: date, mode: str, field: int = 4) -> float:
    return premium(spot, strike, years(at, exp, mode), vix(at, field), kind)


def fees(entry: float, exit_: float) -> float:
    return C.costs((entry + exit_) * LOT)


# --- family 1: option buying = the real bot, replayed --------------------------------------------
def run_bot(mode: str, overrides: dict, out: Path) -> list[dict]:
    import bot
    import review

    sim = [None]
    bot.now = lambda: sim[0]
    _time.sleep = lambda s: sim.__setitem__(0, sim[0] + timedelta(seconds=s))
    saved = {k: getattr(C, k) for k in overrides}
    for k, v in overrides.items():
        setattr(C, k, v)

    class Market:
        def __init__(self, d):
            self.d = d
            e = expiry(d)
            k0 = int(BARS[bisect.bisect_left(STARTS, datetime.combine(d, time(9, 15), IST))][1] // 50 * 50)
            self.chain = [Option(f"{x}|{k}|{t}", f"NIFTY{x:%d%b}{k}{t}".upper(), "NIFTY", x, float(k), t, LOT)
                          for x in (e, e + timedelta(7)) for k in range(k0 - 1500, k0 + 1550, 50) for t in ("CE", "PE")]

        def funds(self):
            return 1_000_000.0  # big account so sizing never blocks a setup; results are read in R

        def spot(self):
            i = bisect.bisect_right(STARTS, sim[0]) - 1
            _, o, hi, lo, c = BARS[i]
            f = min(1.0, (sim[0] - BARS[i][0]).total_seconds() / 300)
            path = [o, lo, hi, c] if c >= o else [o, hi, lo, c]
            seg = min(2, int(f * 3))
            return path[seg] + (path[seg + 1] - path[seg]) * (f * 3 - seg)

        def candles(self, index, days):
            lo = bisect.bisect_left(STARTS, datetime.combine(self.d - timedelta(days), time(0), IST))
            return [(*b, 0.0) for b in BARS[lo:bisect.bisect_right(STARTS, sim[0])]]

        def options(self, index):
            return self.chain

        def ltp(self, keys):
            s, out_ = self.spot(), {}
            for k in keys:
                if k == "NIFTY":
                    out_[k] = s
                elif k == "INDIAVIX":
                    out_[k] = vix(sim[0]) * 100
                else:
                    e, strike, kind = k.split("|")
                    out_[k] = round(price(s, float(strike), kind, sim[0], date.fromisoformat(e), mode), 2)
            return out_

    logging.basicConfig(level=logging.CRITICAL)
    out.mkdir(parents=True, exist_ok=True)
    (out / "journal.csv").unlink(missing_ok=True)
    bot.ROOT = out
    for d in DAYS[1:]:
        sim[0] = datetime.combine(d, time(8, 59), IST)
        bot.connect = lambda name, d=d: Market(d)
        with contextlib.redirect_stdout(io.StringIO()):
            bot.run(False)
    for k, v in saved.items():
        setattr(C, k, v)
    return review.load(out / "journal.csv") if (out / "journal.csv").exists() else []


# --- family 2: option selling, 09:20-style short straddle with per-leg stops ------------------------
def sell_day(day: list, mode: str, sl: float, to_cost: bool, wings: int, start: time, skip_expiry: bool):
    d = day[0][0].date()
    e = expiry(d)
    if skip_expiry and e == d:
        return None
    i = next((j for j, b in enumerate(day) if (b[0] + BAR).time() >= start), None)
    if i is None:
        return None
    t0, s0 = day[i][0] + BAR, day[i][4]
    k = round(s0 / 50) * 50
    legs = [{"kind": "CE", "k": k, "short": True}, {"kind": "PE", "k": k, "short": True}]
    if wings:
        legs += [{"kind": "CE", "k": k + wings, "short": False}, {"kind": "PE", "k": k - wings, "short": False}]
    for g in legs:
        p = price(s0, g["k"], g["kind"], t0, e, mode)
        g["in"] = p * (1 - SLIP) if g["short"] else p * (1 + SLIP)
        g["stop"], g["out"] = g["in"] * (1 + sl), None
    for b in day[i + 1:]:
        end = b[0] + BAR
        for g in legs:
            if g["out"] is None and g["short"]:
                worst = price(b[2] if g["kind"] == "CE" else b[3], g["k"], g["kind"], b[0], e, mode, field=2)
                if worst >= g["stop"]:
                    g["out"] = g["stop"] * (1 + SLIP)
                    for h in legs:
                        if to_cost and h["short"] and h["out"] is None:
                            h["stop"] = min(h["stop"], h["in"])
        if end.time() >= C.SQUARE_OFF or all(g["out"] is not None for g in legs if g["short"]):
            for g in legs:
                if g["out"] is None:
                    p = price(b[4], g["k"], g["kind"], end, e, mode)
                    g["out"] = p * (1 + SLIP) if g["short"] else p * (1 - SLIP)
            break
    return sum(((g["in"] - g["out"]) if g["short"] else (g["out"] - g["in"])) * LOT - fees(g["in"], g["out"])
               for g in legs if g["out"] is not None)


def by_day() -> dict:
    out: dict = {}
    for b in BARS:
        out.setdefault(b[0].date(), []).append(b)
    return out


# --- scoring --------------------------------------------------------------------------------------
def stats(pnl: dict) -> dict:
    """pnl: {date: value}. Profit factor, win days, positive months, max drawdown, per-year totals."""
    vals = [pnl[d] for d in sorted(pnl)]
    if not vals:
        return {"n": 0}
    eq = peak = dd = 0.0
    for v in vals:
        eq += v
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    months: dict = {}
    years_: dict = {}
    for d, v in pnl.items():
        months[d.strftime("%Y-%m")] = months.get(d.strftime("%Y-%m"), 0) + v
        years_[d.year] = years_.get(d.year, 0) + v
    win, loss = sum(v for v in vals if v > 0), -sum(v for v in vals if v < 0)
    return {"n": len(vals), "net": eq, "pf": win / loss if loss else float("inf"), "dd": dd,
            "win": sum(v > 0 for v in vals) / len(vals), "months": sum(v > 0 for v in months.values()) / len(months),
            "years": years_}


def show(name: str, s: dict, unit: str) -> str:
    if not s.get("n"):
        return f"{name:44} no trades"
    yrs = "  ".join(f"{y}:{v:+,.0f}" for y, v in sorted(s["years"].items()))
    return (f"{name:44} days {s['n']:4}  net {s['net']:+10,.0f}{unit}  PF {s['pf']:4.2f}  win {s['win']:3.0%}  "
            f"green months {s['months']:3.0%}  maxDD {s['dd']:9,.0f}{unit}\n{'':44} {yrs}")


def main_buy():
    variants = {
        "breakout (current rules)": {},
        "breakout, entries 09:30-11:00 only": {"ENTRY_END": time(11, 0)},
        "breakout, T1 at 1R": {"T1_R": 1.0},
        "breakout, morning + T1 1R": {"ENTRY_END": time(11, 0), "T1_R": 1.0},
    }
    for mode in ("calendar", "trading"):
        print(f"\n== OPTION BUYING, decay counted by {mode} time (Rs per Rs 1,500 risked per trade) ==")
        for n, (name, ov) in enumerate(variants.items()):
            trades = run_bot(mode, ov, HERE / "lab_out" / f"buy-{mode}-{n}")
            pnl: dict = {}
            for t in trades:  # R x Rs 1,500 = what a Rs 1.5L account at 1% risk would make
                d = date.fromisoformat(t["date"])
                pnl[d] = pnl.get(d, 0) + t["r"] * 1500
            print(show(name, stats(pnl), ""), flush=True)


def main_sell():
    days = by_day()
    grid = [(sl, tc, w, st, sk) for sl in (0.2, 0.3, 0.4, 0.5) for tc in (True, False) for w in (0, 400)
            for st in (time(9, 20), time(9, 45)) for sk in (False, True)]
    split = date(2024, 1, 1)
    rows = []
    for g in grid:
        res = {}
        for mode in ("calendar", "trading"):
            pnl = {d: v for d, b in days.items() if (v := sell_day(b, mode, *g)) is not None}
            res[mode] = (stats({d: v for d, v in pnl.items() if d < split}),
                         stats({d: v for d, v in pnl.items() if d >= split}), stats(pnl))
        rows.append((g, res))
    # choose on 2022-23 only: the setting whose WORSE convention earns most there
    rank = sorted(rows, key=lambda r: -min(r[1]["calendar"][0]["net"], r[1]["trading"][0]["net"]))
    label = lambda g: (f"SL {g[0]:.0%}{' +cost' if g[1] else ''}{' wings ' + str(g[2]) if g[2] else ' naked'} "
                       f"@{g[3]:%H:%M}{' no-expiry-day' if g[4] else ''}")
    print("\n== OPTION SELLING: top 5 settings chosen on 2022-23 (Rs per lot of 65) ==")
    for g, res in rank[:5]:
        print(f"\n# {label(g)}")
        for mode in ("calendar", "trading"):
            ins, oos, _ = res[mode]
            print(show(f"  {mode}: 2022-23 (chosen on)", ins, ""))
            print(show(f"  {mode}: 2024-26 (never seen)", oos, ""))


def main_real():
    """How much does a real ATM straddle lose from 09:20 to 15:15, vs what each model predicts?"""
    opt = {}
    with open(HERE / "data" / "nifty_options_5m.csv") as f:
        for r in csv.DictReader(f):
            opt[(r["expiry"], int(r["strike"]), r["kind"], r["time"][:16])] = float(r["close"])
    expiries = sorted({k[0] for k in opt})
    buckets: dict = {}
    for d, bars in by_day().items():
        b0 = next((b for b in bars if b[0].time() == time(9, 15)), None)
        b1 = next((b for b in bars if b[0].time() == time(15, 10)), None)
        if not b0 or not b1:
            continue
        k = round(b0[4] / 100) * 100
        for e in expiries:
            ed = date.fromisoformat(e)
            dte = (ed - d).days
            if not 1 <= dte <= 35:
                continue
            try:
                real0 = sum(opt[(e, k, x, f"{d}T09:15")] for x in ("CE", "PE"))
                real1 = sum(opt[(e, k, x, f"{d}T15:10")] for x in ("CE", "PE"))
            except KeyError:
                continue
            m = {md: (sum(price(b0[4], k, x, b0[0] + BAR, ed, md) for x in ("CE", "PE")),
                      sum(price(b1[4], k, x, b1[0] + BAR, ed, md) for x in ("CE", "PE"))) for md in ("calendar", "trading")}
            key = "1" if dte == 1 else "2-3" if dte <= 3 else "4-7" if dte <= 7 else "8-14" if dte <= 14 else "15-35"
            buckets.setdefault(key, []).append((real0, real1, m))
    print("ATM straddle, sold 09:20 and bought back 15:15 (Rs per unit; + = seller gains)")
    print(f"{'days to expiry':15} {'samples':>7} | {'price @09:20 real / cal / trd':>32} | {'09:20->15:15 decay real / cal / trd':>38}")
    for key in ("1", "2-3", "4-7", "8-14", "15-35"):
        rows = buckets.get(key, [])
        if not rows:
            continue
        n = len(rows)
        avg = lambda f: sum(f(r) for r in rows) / n
        p0 = (avg(lambda r: r[0]), avg(lambda r: r[2]["calendar"][0]), avg(lambda r: r[2]["trading"][0]))
        dk = (avg(lambda r: r[0] - r[1]), avg(lambda r: r[2]["calendar"][0] - r[2]["calendar"][1]),
              avg(lambda r: r[2]["trading"][0] - r[2]["trading"][1]))
        print(f"{key:15} {n:7} | {p0[0]:9.1f} / {p0[1]:8.1f} / {p0[2]:8.1f} | {dk[0]:+11.1f} / {dk[1]:+9.1f} / {dk[2]:+9.1f}")


if __name__ == "__main__":
    {"buy": main_buy, "sell": main_sell, "real": main_real}[sys.argv[1]]()
