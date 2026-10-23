"""Checks for the money paths. Run: python test_core.py"""
from datetime import date, datetime, timedelta

import brain
import config as C
import risk
from brokers import IST, Option
from brokers.paper import Paper


def bars_for(day: date, start: float, moves: list[float]) -> list:
    out, px, t = [], start, datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST)
    for m in moves:
        o, c = px, px + m
        out.append((t, o, max(o, c) + 1, min(o, c) - 1, c, 1000))
        px, t = c, t + timedelta(minutes=5)
    return out


PREV = bars_for(date(2026, 10, 20), 25000, [3, -3] * 37 + [0])
TODAY = bars_for(date(2026, 10, 21), 25010, [7, -3] * 6 + [7])  # rising zigzag ending in a breakout bar
NOW = TODAY[-1][0] + brain.BAR


def test_chart_and_market_find_the_long():
    bars = PREV + TODAY
    s, why = brain.chart("NIFTY", bars, NOW)
    assert s and s.side == "LONG", why
    assert s.sl < s.entry < s.t1 < s.t2
    assert brain.market(bars, NOW, 14.0, {})[0] == {"LONG"}
    assert brain.market(bars, NOW, 30.0, {})[0] == set()  # VIX veto
    assert brain.market(bars, NOW, 14.0, {"skip_day": True})[0] == set()  # research veto
    assert brain.market(bars, NOW, 14.0, {"blackout": [["10:00", "10:30"]]})[0] == set()
    assert brain.chart("NIFTY", PREV + TODAY[:3], NOW)[0] is None  # opening range still forming


def test_forming_bar_is_ignored():
    assert brain.closed(TODAY, TODAY[-1][0] + timedelta(minutes=2)) == TODAY[:-1]


def test_gate_caps_trades_losses_and_time():
    at = lambda h, m: datetime(2026, 10, 21, h, m, tzinfo=IST)
    assert risk.gate(at(10, 0), 0, 0, 0, 100_000, False) is None
    assert risk.gate(at(10, 0), C.MAX_TRADES, 0, 0, 100_000, False)  # trade cap
    assert risk.gate(at(10, 0), 1, 0, -C.DAILY_LOSS_PCT * 100_000, 100_000, False)  # daily loss
    assert risk.gate(at(10, 0), 1, C.MAX_CONSEC_LOSSES, 0, 100_000, False)  # losing streak
    assert risk.gate(at(9, 20), 0, 0, 0, 100_000, False)  # opening range
    assert risk.gate(at(14, 45), 0, 0, 0, 100_000, False)  # too late
    assert risk.gate(at(10, 0), 0, 0, 0, 100_000, True)  # already in a trade


def test_size_never_exceeds_risk_budget():
    s = brain.Setup("NIFTY", "LONG", 25000, 24976, 25036, 25072, "")
    lots, why = risk.size(s, 180, 65, 150_000, 150_000)
    assert lots >= 1, why
    max_loss = (C.DELTA * 24 * 1.1 + 0.5) * lots * 65
    assert max_loss <= C.RISK_PCT * 150_000
    assert risk.size(s, 180, 65, 20_000, 20_000)[0] == 0  # too small an account: reject, never force 1 lot


def test_exit_rules():
    s = brain.Setup("NIFTY", "LONG", 25000, 24980, 25030, 25060, "")
    t = brain.Trade(s, lots=2, sl=s.sl)
    ten = datetime(2026, 10, 21, 10, 0, tzinfo=IST)
    assert brain.check_exit(t, 25035, 24975, ten) == ("stop loss", 2)  # both touched: assume the stop
    assert brain.check_exit(t, 25031, 24990, ten) == ("target 1", 1)  # half off at T1
    assert brain.check_exit(brain.Trade(s, lots=1, sl=s.sl), 25031, 24990, ten) == ("target 1", 0)
    assert brain.check_exit(t, 25010, 24990, ten.replace(hour=15, minute=15))[0] == "EOD square-off"
    short = brain.Trade(brain.Setup("NIFTY", "SHORT", 25000, 25020, 24970, 24940, ""), lots=1, sl=25020)
    assert brain.check_exit(short, 25021, 24990, ten)[0] == "stop loss"
    assert brain.check_exit(short, 25000, 24939, ten)[0] == "target 2"


def test_option_pick_skips_expiry_day_and_goes_one_itm():
    today = date(2026, 10, 20)
    chain = [Option(f"k{e}{k}{x}", f"N{e}{k}{x}", "NIFTY", e, k, x, 65)
             for e in (today, date(2026, 10, 27)) for k in range(24800, 25250, 50) for x in ("CE", "PE")]
    up = brain.Setup("NIFTY", "LONG", 25012, 0, 0, 0, "")
    o = brain.pick_option(up, chain, 25012, today)
    assert (o.expiry, o.strike, o.kind) == (date(2026, 10, 27), 24950, "CE")
    o = brain.pick_option(brain.Setup("NIFTY", "SHORT", 25012, 0, 0, 0, ""), chain, 25012, today)
    assert (o.strike, o.kind) == (25050, "PE")
    assert brain.pick_option(up, chain, 26000, today) is None  # wanted strike not listed: no trade


def test_paper_fills_and_cash():
    class Fake:
        def funds(self): return 100_000.0
        def ltp(self, keys): return {k: 100.0 for k in keys}
    p = Paper(Fake())
    opt = Option("k", "SYM", "NIFTY", date(2026, 10, 27), 25000, "CE", 65)
    oid = p.place(opt, "BUY", 65, 101.0)
    assert p.order(oid)["status"] == "COMPLETE" and p.funds() < 100_000
    assert p.order(p.place(opt, "BUY", 65, 99.0))["status"] == "OPEN"  # limit below market waits


def test_review_explains_wins_and_losses():
    import review
    base = {"stretch_atr": 0.5, "trend_atr": 0.8, "in": "10:00", "dte": 3, "vix": 14, "mae_r": -0.2}
    loss = {**base, "pnl": -900, "exits": ["stop loss"]}
    assert review.diagnose({**loss, "mfe_r": 0.1})[0] == "FALSE BREAKOUT"
    assert review.diagnose({**loss, "mfe_r": 0.9})[0] == "REVERSED BEFORE T1"
    assert "chasing" in review.diagnose({**loss, "mfe_r": 0.0, "stretch_atr": 2.0})[1]
    assert review.diagnose({**base, "pnl": 2500, "exits": ["target 1", "target 2"], "mfe_r": 3})[0] == "TREND RUN"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
