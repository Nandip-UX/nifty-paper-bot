"""The analysts: chart, market and F&O agents plus the trade manager's exit rules.
Pure functions (candles in, decisions out), shared by the live bot and the backtest."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import config as C
from brokers import Candle, Option

BAR = timedelta(minutes=5)


@dataclass
class Setup:
    index: str
    side: str  # LONG (buy CE) | SHORT (buy PE)
    entry: float  # index level at the signal
    sl: float
    t1: float
    t2: float
    why: str
    ctx: dict = field(default_factory=dict)  # entry conditions, kept in the journal for review


@dataclass
class Trade:
    s: Setup
    lots: int
    sl: float  # live index stop, moves to entry once T1 is booked
    t1_done: bool = False
    opt: Option | None = None
    prem: float = 0.0  # average entry premium
    opened: datetime | None = None
    stop_id: str | None = None  # broker-side disaster stop (live only)
    pnl: float = 0.0  # realised so far, net of costs
    risk_rs: float = 0.0  # planned loss at the stop, for results in R
    mfe: float = 0.0  # best index move in our favour since entry, points
    mae: float = 0.0  # worst index move against us since entry, points (<= 0)


# --- indicators ---------------------------------------------------------------
def ema(xs: list[float], n: int) -> list[float]:
    k, out = 2 / (n + 1), []
    for x in xs:
        out.append(x if not out else out[-1] + k * (x - out[-1]))
    return out


def rsi(closes: list[float], n: int = 14) -> float:
    gain = loss = 0.0  # Wilder smoothing
    for a, b in zip(closes, closes[1:]):
        gain = (gain * (n - 1) + max(b - a, 0)) / n
        loss = (loss * (n - 1) + max(a - b, 0)) / n
    return 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)


def atr(bars: list[Candle], n: int = 14) -> float:
    """Wilder ATR; the first bar of each day uses its own range so overnight gaps don't inflate it."""
    trs = [
        c[2] - c[3] if i == 0 or c[0].date() != bars[i - 1][0].date()
        else max(c[2], bars[i - 1][4]) - min(c[3], bars[i - 1][4])
        for i, c in enumerate(bars)
    ]
    return ema(trs, 2 * n - 1)[-1]


def closed(candles: list[Candle], now: datetime) -> list[Candle]:
    """Drop the bar still forming; brokers often return it."""
    return [c for c in candles if c[0] + BAR <= now]


def split(bars: list[Candle], today: date) -> tuple[list[Candle], list[Candle]]:
    """(today's bars, previous trading day's bars)."""
    day = [c for c in bars if c[0].date() == today]
    older = [c for c in bars if c[0].date() < today]
    prev = [c for c in older if c[0].date() == older[-1][0].date()] if older else []
    return day, prev


# --- 1. chart agent -------------------------------------------------------------
def chart(index: str, bars: list[Candle], now: datetime) -> tuple[Setup | None, str]:
    """A 5-min close through the last 30-min range, with trend, momentum and room to T1."""
    day, prev = split(bars, now.date())
    if len(day) < 4 or not prev:  # 9:15-9:30 opening range + one trigger bar
        return None, "opening range forming"
    pdh, pdl, pdc = max(c[2] for c in prev), min(c[3] for c in prev), prev[-1][4]
    closes = [c[4] for c in bars]
    e9, e21, e50 = ema(closes, 9)[-1], ema(closes, 21)[-1], ema(closes, 50)[-1]
    r, a = rsi(closes), atr(bars)
    _, o, h, l, c, _ = day[-1]
    window = day[-1 - C.BREAKOUT_BARS : -1]
    hh, ll = max(x[2] for x in window), min(x[3] for x in window)
    strong = abs(c - o) >= 0.5 * (h - l) and h - l <= 2 * a  # decisive body, not a spike

    if c > hh and c > o and strong and e9 > e21 and c > e50 and 55 <= r <= 75:
        side, sign, broke = "LONG", 1, hh
    elif c < ll and c < o and strong and e9 < e21 and c < e50 and 25 <= r <= 45:
        side, sign, broke = "SHORT", -1, ll
    else:
        return None, f"no setup: close {c:.1f} inside {ll:.1f}-{hh:.1f}, rsi {r:.0f}, ema9/21 {e9:.1f}/{e21:.1f}"

    risk = C.ATR_SL * a
    sl, t1, t2 = c - sign * risk, c + sign * C.T1_R * risk, c + sign * C.T2_R * risk
    wall = [lv for lv in (pdh, pdl, pdc) if min(c, t1) < lv < max(c, t1)]
    if wall:
        return None, f"{side} skipped: prior-day level {wall[0]:.1f} sits before T1"
    why = (f"{side} {index}: close {c:.1f} broke 30-min {'high' if sign > 0 else 'low'} {broke:.1f}, "
           f"ema9{'>' if sign > 0 else '<'}ema21 trend, rsi {r:.0f}, atr {a:.1f}, PDH/PDL/PDC {pdh:.0f}/{pdl:.0f}/{pdc:.0f}")
    ctx = {"rsi": round(r if sign > 0 else 100 - r, 1), "atr": round(a, 1), "risk_pts": round(risk, 1),
           "trend_atr": round(sign * (e9 - e21) / a, 2), "stretch_atr": round(sign * (c - e21) / a, 2),
           "day_pct": round(sign * (c - pdc) / pdc * 100, 2)}  # all signed: + = in the trade's favour
    return Setup(index, side, c, sl, t1, t2, why, ctx), why


# --- 2. market agent ------------------------------------------------------------
def market(bars: list[Candle], now: datetime, vix: float, brief: dict) -> tuple[set[str], str]:
    """Which directions today's context allows: trade with the day, never against it."""
    if vix > C.VIX_MAX:
        return set(), f"India VIX {vix:.1f} above {C.VIX_MAX}"
    if brief.get("skip_day"):
        return set(), f"research veto: {brief.get('reason', '')}"
    hm = now.strftime("%H:%M")
    for start, end in brief.get("blackout", []):
        if start <= hm < end:
            return set(), f"event blackout {start}-{end}"
    day, prev = split(bars, now.date())
    if not day or not prev:
        return set(), "no context yet"
    last, day_open, pdc = day[-1][4], day[0][1], prev[-1][4]
    if last > pdc and last > day_open:
        return {"LONG"}, f"bullish day: {last:.1f} above open {day_open:.1f} and prev close {pdc:.1f}"
    if last < pdc and last < day_open:
        return {"SHORT"}, f"bearish day: {last:.1f} below open {day_open:.1f} and prev close {pdc:.1f}"
    return set(), f"mixed day: {last:.1f} between open {day_open:.1f} and prev close {pdc:.1f}"


# --- 3. F&O agent ---------------------------------------------------------------
def pick_option(s: Setup, chain: list[Option], spot: float, today: date) -> Option | None:
    """Nearest expiry that is not today (no expiry-day theta crush), one strike in the money."""
    kind = "CE" if s.side == "LONG" else "PE"
    live = [o for o in chain if o.kind == kind and o.expiry > today]
    if not live:
        return None
    expiry = min(o.expiry for o in live)
    live = [o for o in live if o.expiry == expiry]
    strikes = sorted({o.strike for o in live})
    step = min(b - a for a, b in zip(strikes, strikes[1:]))
    atm = round(spot / step) * step
    want = atm - C.ITM_STEPS * step if kind == "CE" else atm + C.ITM_STEPS * step
    best = min(live, key=lambda o: abs(o.strike - want))
    return best if abs(best.strike - want) < step else None


# --- 6. trade manager rules -----------------------------------------------------
def check_exit(t: Trade, hi: float, lo: float, now: datetime) -> tuple[str, int] | None:
    """(reason, lots to sell) for the index range seen since the last check. Stop is checked
    before targets, so a bar touching both counts as a loss (the conservative read)."""
    up = t.s.side == "LONG"
    if now.time() >= C.SQUARE_OFF:
        return "EOD square-off", t.lots
    if (lo <= t.sl) if up else (hi >= t.sl):
        return ("breakeven stop" if t.t1_done else "stop loss"), t.lots
    if (hi >= t.s.t2) if up else (lo <= t.s.t2):
        return "target 2", t.lots
    if not t.t1_done and ((hi >= t.s.t1) if up else (lo <= t.s.t1)):
        return "target 1", t.lots // 2  # 0 with a single lot: just move the stop to entry
    return None


def fading(t: Trade, bars: list[Candle]) -> bool:
    """After T1, a 5-min close back through EMA9 ends the move."""
    if not t.t1_done:
        return False
    c, e9 = bars[-1][4], ema([b[4] for b in bars], 9)[-1]
    return c < e9 if t.s.side == "LONG" else c > e9
