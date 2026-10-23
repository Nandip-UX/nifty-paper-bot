"""Trading commander. Runs one intraday session, 09:00 -> ~15:20 IST, then writes the day report.

    python bot.py            paper: real prices + real balance, simulated orders (default)
    python bot.py --live     real orders through the broker in config.BROKER
    touch STOP               kill switch: squares off and stops trading for the day
"""
import argparse
import csv
import logging
import os
import sys
import time as clock
from datetime import datetime, time
from pathlib import Path

import brain
import config as C
import research
import review
import risk
from brokers import IST, connect, tick
from brokers.paper import Paper

ROOT = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parent)  # journal, reports, logs, STOP
STOP = ROOT / "STOP"
log = logging.getLogger("bot")


def now() -> datetime:
    return datetime.now(IST)


class Day:
    def __init__(self, b, live: bool):
        self.b, self.live = b, live
        self.balance = b.funds()  # risk is sized off the start-of-day balance
        self.trades = self.streak = 0
        self.pnl = 0.0
        self.trade: brain.Trade | None = None
        self.rows: list[dict] = []  # closed legs, for the journal and report
        self.notes: list[str] = []  # setups the agents turned down, and why
        self.halted = ""
        self.last_gate = ""
        self.brief = research.premarket(now().date())
        self.chains = {i: b.options(i) for i in C.INDICES}
        log.info("balance Rs %s | mode %s | broker %s | indices %s",
                 f"{self.balance:,.0f}", "LIVE" if live else "paper", C.BROKER, C.INDICES)

    # --- every 5-minute bar close: research the market, look for a setup ------------
    def on_bar(self, n: datetime):
        for idx in C.INDICES:
            bars = brain.closed(self.b.candles(idx, 7), n)
            if n.time() >= time(9, 25) and not any(c[0].date() == n.date() for c in bars):
                self.halted = "no candles today (market holiday?)"
                return
            t = self.trade
            if t and t.s.index == idx and brain.fading(t, bars):
                self.close(t.lots, "trend fading after T1")
            gate = self.halted or risk.gate(n, self.trades, self.streak, self.pnl, self.balance, bool(self.trade))
            if gate:
                if gate != self.last_gate:
                    log.info("risk gate: %s", gate)
                self.last_gate = gate
                continue
            self.last_gate = ""
            vix = self.b.ltp(["INDIAVIX"])["INDIAVIX"]
            sides, ctx = brain.market(bars, n, vix, self.brief)
            setup, why = brain.chart(idx, bars, n)
            log.info("%s | market: %s | chart: %s", idx, ctx, why)
            if setup:
                setup.ctx["vix"] = round(vix, 1)
                self.consider(setup, sides, ctx, n)

    def consider(self, s: brain.Setup, sides: set[str], ctx: str, n: datetime):
        stamp = f"{n:%H:%M} {s.index} {s.side}"
        if s.side not in sides:
            return self.notes.append(f"{stamp}: chart setup against the market ({ctx})")
        spot = self.b.ltp([s.index])[s.index]
        if abs(spot - s.entry) > 0.3 * abs(s.entry - s.sl):
            return self.notes.append(f"{stamp}: price ran {spot - s.entry:+.1f} pts from signal, not chasing")
        opt = brain.pick_option(s, self.chains[s.index], spot, n.date())
        if not opt:
            return self.notes.append(f"{stamp}: no suitable option contract")
        prem = self.b.ltp([opt.key])[opt.key]
        lots, verdict = risk.size(s, prem, opt.lot, self.balance, self.b.funds())
        log.info("F&O: %s @ %.2f | risk: %s", opt.symbol, prem, verdict)
        if not lots:
            return self.notes.append(f"{stamp} {opt.symbol}: {verdict}")
        self.enter(s, opt, lots)

    # --- 5. execution ----------------------------------------------------------------
    def fill(self, opt, side: str, qty: int) -> tuple[int, float]:
        """Marketable LIMIT orders, up to 3 tries at 1/2/3% through the last price."""
        done, value = 0, 0.0
        for step in (0.01, 0.02, 0.03):
            try:
                st = self.attempt(opt, side, qty - done, step)
            except Exception as e:  # keep what already filled; caller decides what to do with the rest
                log.error("%s %s order error: %s", side, opt.symbol, e)
                break
            done += st["filled"]
            value += st["filled"] * st["avg"]
            if st["status"] == "REJECTED":
                log.error("%s %s rejected: %s", side, opt.symbol, st["msg"])
                break
            if done >= qty:
                break
        return done, (value / done if done else 0.0)

    def attempt(self, opt, side: str, qty: int, step: float) -> dict:
        px = self.b.ltp([opt.key])[opt.key]
        oid = self.b.place(opt, side, qty, tick(px * (1 + step if side == "BUY" else 1 - step)))
        for _ in range(10):
            st = self.b.order(oid)
            if st["status"] != "OPEN":
                return st
            clock.sleep(1)
        try:
            self.b.cancel(oid)
        except Exception as e:  # it may have filled in the meantime
            log.warning("cancel %s: %s", oid, e)
        clock.sleep(1)
        # ponytail: a fill landing after this read, or an error mid-poll, goes untracked; reconcile with broker positions if it ever happens
        return self.b.order(oid)

    def enter(self, s: brain.Setup, opt, lots: int):
        got, avg = self.fill(opt, "BUY", lots * opt.lot)
        if not got:
            return self.notes.append(f"{now():%H:%M} {opt.symbol}: entry order not filled")
        self.trades += 1
        self.trade = brain.Trade(s, lots=got // opt.lot, sl=s.sl, opt=opt, prem=avg, opened=now(),
                                 risk_rs=risk.unit_risk(s) * (got // opt.lot) * opt.lot)
        log.info("ENTRY #%d %s x%d lots @ %.2f | index SL %.1f T1 %.1f T2 %.1f | %s",
                 self.trades, opt.symbol, got // opt.lot, avg, s.sl, s.t1, s.t2, s.why)
        self.protect()

    def protect(self):
        """Live only: a broker-side stop, so a crash or lost connection can't leave the option unguarded."""
        t = self.trade
        if not self.live or not t.lots:
            return
        trig = tick(t.prem - 1.5 * C.DELTA * abs(t.s.entry - t.s.sl))
        try:
            t.stop_id = self.b.place(t.opt, "SELL", t.lots * t.opt.lot, tick(trig * 0.9), trigger=trig)
        except Exception as e:
            log.error("could not place broker-side stop (%s); bot-side stop still active", e)

    def close(self, lots: int, reason: str):
        t, lot = self.trade, self.trade.opt.lot
        if t.stop_id:  # pull the broker stop first so the position is never sold twice
            try:
                self.b.cancel(t.stop_id)
            except Exception as e:
                log.warning("cancel stop: %s", e)
            st, t.stop_id = self.b.order(t.stop_id), None
            if st["filled"]:
                self.book(st["filled"] // lot, st["avg"], "broker-side stop")
                lots = min(lots, t.lots)
        if lots and t.lots:
            got, avg = self.fill(t.opt, "SELL", lots * lot)
            if got:
                self.book(got // lot, avg, reason)
            if got < lots * lot:
                log.critical("EXIT INCOMPLETE: %d of %d units sold of %s, retrying next tick", got, lots * lot, t.opt.symbol)
        if t.lots:
            self.protect()
        else:
            self.streak = self.streak + 1 if t.pnl < 0 else 0
            log.info("CLOSED %s net Rs %s | day Rs %s", t.opt.symbol, f"{t.pnl:,.0f}", f"{self.pnl:,.0f}")
            self.trade = None

    def book(self, lots: int, price: float, reason: str):
        t = self.trade
        qty = lots * t.opt.lot
        pnl = (price - t.prem) * qty - C.costs((price + t.prem) * qty)
        t.lots -= lots
        t.pnl += pnl
        self.pnl += pnl
        row = {"date": f"{now():%Y-%m-%d}", "in": f"{t.opened:%H:%M}", "out": f"{now():%H:%M}",
               "contract": t.opt.symbol, "side": t.s.side, "lots": lots, "entry": round(t.prem, 2),
               "exit": round(price, 2), "reason": reason, "pnl": round(pnl, 2), "risk_rs": round(t.risk_rs),
               "mfe_r": round(t.mfe / t.s.ctx["risk_pts"], 2), "mae_r": round(t.mae / t.s.ctx["risk_pts"], 2),
               "dte": (t.opt.expiry - t.opened.date()).days, **t.s.ctx, "why": t.s.why}
        self.rows.append(row)
        path = ROOT / "journal.csv"
        new = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=row)
            if new:
                w.writeheader()
            w.writerow(row)
        log.info("EXIT %s x%d lots @ %.2f (%s) Rs %s", t.opt.symbol, lots, price, reason, f"{pnl:,.0f}")

    # --- 6. trade manager, every POLL_SEC ----------------------------------------------
    def manage(self):
        t = self.trade
        if t.stop_id and self.b.order(t.stop_id)["status"] == "COMPLETE":
            return self.close(t.lots, "broker-side stop")
        if STOP.exists():
            return self.close(t.lots, "kill switch")
        px = self.b.ltp([t.s.index, t.opt.key])
        fav = (px[t.s.index] - t.s.entry) * (1 if t.s.side == "LONG" else -1)
        t.mfe, t.mae = max(t.mfe, fav), min(t.mae, fav)
        if px[t.opt.key] <= t.prem - 1.3 * C.DELTA * abs(t.s.entry - t.s.sl):
            return self.close(t.lots, "premium stop (option fell faster than the index)")
        ex = brain.check_exit(t, px[t.s.index], px[t.s.index], now())
        if not ex:
            return
        reason, lots = ex
        if reason == "target 1":
            t.t1_done, t.sl = True, t.s.entry
            log.info("T1 reached on %s: stop moved to breakeven %.1f", t.s.index, t.sl)
            if not lots:
                return
        self.close(lots, reason)

    def report(self) -> str:
        wins = sum(1 for r in self.rows if r["pnl"] > 0)
        lines = [
            f"# Trading day {now():%Y-%m-%d} ({'LIVE' if self.live else 'paper'}, {C.BROKER})",
            "",
            f"Start balance Rs {self.balance:,.0f} | entries {self.trades}/{C.MAX_TRADES} | "
            f"exits {len(self.rows)} ({wins} green) | **net P&L Rs {self.pnl:,.0f} "
            f"({self.pnl / self.balance:+.2%})**" if self.balance else "No balance read.",
        ]
        if self.halted:
            lines.append(f"Stopped early: {self.halted}")
        if self.brief:
            lines += ["", f"Research: bias {self.brief['bias']}; {self.brief['reason']}", "", self.brief["summary"]]
        if self.rows:
            lines += ["", "| in | out | contract | side | lots | entry | exit | reason | P&L |", "|" + "---|" * 9]
            lines += [f"| {r['in']} | {r['out']} | {r['contract']} | {r['side']} | {r['lots']} | {r['entry']} | "
                      f"{r['exit']} | {r['reason']} | {r['pnl']:,.0f} |" for r in self.rows]
        if self.rows:
            today = [t for t in review.load(ROOT / "journal.csv") if t["date"] == f"{now():%Y-%m-%d}"]
            lines += ["", "Why each trade worked or failed:"] + [review.line(t) for t in today]
        if (ROOT / "journal.csv").exists():
            lines += ["", "All trades since the journal started: " + review.summary(review.load(ROOT / "journal.csv"))]
        if self.notes:
            lines += ["", "Setups the agents turned down:"] + [f"- {x}" for x in self.notes]
        text = "\n".join(lines) + "\n"
        (ROOT / "reports").mkdir(parents=True, exist_ok=True)
        (ROOT / "reports" / f"{now():%Y-%m-%d}.md").write_text(text)
        return text


def run(live: bool):
    n = now()
    if n.weekday() >= 5 or n.time() >= C.SQUARE_OFF:
        return log.info("market closed for today")
    b = connect(C.BROKER)  # logs in now (may ask for today's token)
    if not live:
        b = Paper(b)
    while now().time() < C.RESEARCH_AT:
        clock.sleep(20)
    day, last_bar = Day(b, live), None
    while True:
        try:
            n = now()
            if STOP.exists() and not day.halted:
                day.halted = "kill switch (STOP file)"
            if day.trade:
                day.manage()
            bar = n.replace(minute=n.minute - n.minute % 5, second=0, microsecond=0)
            if bar != last_bar and n.second >= 3 and n.time() >= time(9, 20):
                last_bar = bar
                day.on_bar(n)
            if (n.time() >= C.SQUARE_OFF or day.halted) and not day.trade:
                break
            if n.time() >= time(15, 29):
                log.critical("session ending with %s still open: check the broker NOW", day.trade.opt.symbol)
                break
        except Exception:  # a network blip must not kill the manager of an open position
            log.exception("loop error, retrying")
        clock.sleep(C.POLL_SEC)
    print(day.report())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="place real orders")
    live = ap.parse_args().live
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "logs" / f"{now():%Y-%m-%d}.log")],
    )
    if live and C.BROKER == "yahoo":
        sys.exit("BROKER=yahoo is for paper trading only; set a real broker in .env to go live")
    if live and input(f"LIVE trading on {C.BROKER} with real money. Type LIVE to continue: ") != "LIVE":
        sys.exit("aborted")
    run(live)
