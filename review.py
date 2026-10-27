"""Trade review: why each trade worked or failed, and which conditions win or lose over time.

    python review.py                  the last trading day in journal.csv, trade by trade
    python review.py --all            every trade, plus win/loss by condition
    python review.py --all FILE.csv   same, for another journal (e.g. a replay)

R = result in units of the planned risk: -1R = a full stop-out, +2R = twice the risk won.
"""
import argparse
import csv
from pathlib import Path

import config as C

NUM = ("pnl", "risk_rs", "mfe_r", "mae_r", "dte", "rsi", "atr", "risk_pts", "trend_atr", "stretch_atr", "day_pct", "vix")


def load(path) -> list[dict]:
    """Journal rows (one per exit) -> one dict per trade, with a verdict and a lesson."""
    trades: dict = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            t = trades.setdefault((r["date"], r["in"], r["contract"]), {**r, "pnl": 0.0, "exits": []})
            t["pnl"] += float(r["pnl"])
            t["exits"].append(r["reason"])
            t["mfe_r"], t["mae_r"] = r["mfe_r"], r["mae_r"]  # the last exit holds the final excursion
    for t in trades.values():
        for k in NUM:
            t[k] = float(t.get(k) or 0)
        t["r"] = t["pnl"] / t["risk_rs"] if t["risk_rs"] else 0.0
        t["verdict"], t["lesson"] = diagnose(t)
    return list(trades.values())


def warnings(t: dict) -> list[str]:
    """Entry conditions that the trade history may show to be weak."""
    w = []
    if t["stretch_atr"] > 1.5:
        w.append(f"entry stretched {t['stretch_atr']:.1f} ATR past EMA21 (chasing)")
    if t["trend_atr"] < 0.3:
        w.append(f"weak trend (EMA9-21 gap {t['trend_atr']:.2f} ATR)")
    if t["in"] >= "13:00":
        w.append("afternoon entry (less time to work)")
    if t["dte"] <= 1:
        w.append("1 day to expiry (fast time decay)")
    if 0 < t["vix"] < 12:
        w.append(f"quiet market (VIX {t['vix']:.1f})")
    return w


def diagnose(t: dict) -> tuple[str, str]:
    ex, mfe, mae = t["exits"], t["mfe_r"], t["mae_r"]
    if t["pnl"] > 0:
        if "target 2" in ex:
            return "TREND RUN", f"broke out and ran to T2 ({C.T2_R:.0f}R); worst point {mae:+.1f}R"
        if any("fading" in e for e in ex):
            return "WORKED", f"hit T1, rest exited when the trend faded; best {mfe:+.1f}R"
        return "SMALL WIN", f"{', '.join(ex)}; best {mfe:+.1f}R"
    why = "; ".join(warnings(t)) or "no warning sign at entry"
    if any("premium" in e for e in ex):
        return "OPTION DECAY", f"the option lost value faster than the index moved ({why})"
    if "breakeven stop" in ex:
        half = "booked half at T1, " if len(ex) > 1 else "reached T1, "
        return "SCRATCH", f"{half}then stopped at the entry level; costs and time decay made it red"
    if "EOD square-off" in ex:
        return "NO FOLLOW-THROUGH", f"never reached target or stop, closed at 15:15 ({why})"
    if mfe < 0.3:
        return "FALSE BREAKOUT", f"price never moved our way (best {mfe:+.1f}R), the breakout failed at once ({why})"
    return "REVERSED BEFORE T1", f"was up {mfe:+.1f}R, then reversed to the stop; T1 at {C.T1_R}R was not reached ({why})"


def line(t: dict) -> str:
    return f"- {t['in']} {t['contract']} {t['side']}: Rs {t['pnl']:,.0f} ({t['r']:+.1f}R) **{t['verdict']}**: {t['lesson']}"


def bucket(name: str, key, trades: list[dict]) -> list[str]:
    groups: dict = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    out = [f"\n{name}", f"  {'':22} trades  win%   avg R    net Rs"]
    for k in sorted(groups):
        g = groups[k]
        avg = sum(t["r"] for t in g) / len(g)
        flag = "  <- losing pattern, test a rule against it" if len(g) >= 10 and avg < -0.25 else \
               "  <- strong" if len(g) >= 10 and avg > 0.25 else ""
        out.append(f"  {k:22} {len(g):6} {sum(t['pnl'] > 0 for t in g) / len(g):5.0%} {avg:+7.2f} "
                   f"{sum(t['pnl'] for t in g):9,.0f}{flag}")
    return out


def summary(trades: list[dict]) -> str:
    byday: dict = {}
    for t in trades:
        byday[t["date"]] = byday.get(t["date"], 0) + t["pnl"]
    equity = peak = dd = 0.0
    for d in sorted(byday):
        equity += byday[d]
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return (f"{len(trades)} trades on {len(byday)} days, win rate {sum(t['pnl'] > 0 for t in trades) / len(trades):.0%}, "
            f"avg {sum(t['r'] for t in trades) / len(trades):+.2f}R, **net Rs {equity:,.0f}**, "
            f"green days {sum(v > 0 for v in byday.values())}/{len(byday)}, max drawdown Rs {dd:,.0f}, "
            f"best day Rs {max(byday.values()):,.0f}, worst day Rs {min(byday.values()):,.0f}")


def patterns(trades: list[dict]) -> str:
    cut = lambda v, edges, labels: next((lb for e, lb in zip(edges, labels) if v < e), labels[-1])
    out = [summary(trades)]
    if len(trades) < 30:
        out.append("Fewer than 30 trades: too few to change any rule yet. Keep collecting.")
    out += bucket("Outcome type", lambda t: t["verdict"], trades)
    out += bucket("Side", lambda t: t["side"], trades)
    out += bucket("Entry time", lambda t: cut(t["in"], ["11:00", "13:00"], ["09:30-11:00", "11:00-13:00", "13:00-14:30"]), trades)
    out += bucket("Trend strength (EMA9-21)", lambda t: cut(t["trend_atr"], [0.3, 0.6], ["weak <0.3 ATR", "0.3-0.6 ATR", "strong >0.6 ATR"]), trades)
    out += bucket("Stretch from EMA21", lambda t: cut(t["stretch_atr"], [1.0, 1.5], ["near <1 ATR", "1-1.5 ATR", "stretched >1.5 ATR"]), trades)
    out += bucket("RSI in trade direction", lambda t: cut(t["rsi"], [62, 68], ["55-62", "62-68", "68-75"]), trades)
    out += bucket("India VIX", lambda t: cut(t["vix"], [13, 16], ["<13", "13-16", "16+"]), trades)
    out += bucket("Days to expiry", lambda t: cut(t["dte"], [2, 4], ["1", "2-3", "4+"]), trades)
    out.append("\nChange one rule at a time, only for a pattern with 30+ trades, and keep it only if the"
               "\n1-year backtest improves in both halves of the data.")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("journal", nargs="?", default=Path(__file__).with_name("journal.csv"))
    a = ap.parse_args()
    if not Path(a.journal).exists():
        raise SystemExit("no journal yet: run the bot for a day first")
    trades = load(a.journal)
    days = sorted({t["date"] for t in trades})
    for d in days if a.all else days[-1:]:
        print(f"\n## {d}  (day net Rs {sum(t['pnl'] for t in trades if t['date'] == d):,.0f})")
        print("\n".join(line(t) for t in trades if t["date"] == d))
    print("\n## Patterns so far\n" + patterns(trades))
