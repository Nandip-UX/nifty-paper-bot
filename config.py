"""Every number the bot trades by. Edit here, nowhere else."""
import os
from datetime import time
from pathlib import Path

# .env loader (KEY=value lines); real environment variables win
_env = Path(__file__).with_name(".env")
if _env.exists():
    for line in _env.read_text().splitlines():
        k, sep, v = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

BROKER = os.getenv("BROKER", "zerodha")  # zerodha | upstox | dhan | angel
INDICES = ["NIFTY"]  # scanned in this order; add "BANKNIFTY" / "FINNIFTY" if wanted

# --- hard limits (risk gate refuses anything outside these) ---
MAX_TRADES = 3  # entries per day
RISK_PCT = 0.01  # max loss per trade, share of start-of-day balance
DAILY_LOSS_PCT = 0.03  # stop for the day once realised loss reaches this
MAX_CONSEC_LOSSES = 2  # stop for the day after this many losers in a row
MAX_POSITION_PCT = 0.5  # max premium outlay per trade, share of balance
MAX_LOTS = 10  # absolute cap, guards against a bad balance read
VIX_MAX = 25.0  # skip the day above this India VIX
assert 1 <= MAX_TRADES <= 4, "intraday plan allows 3-4 trades a day, never more"
assert RISK_PCT <= 0.02 and DAILY_LOSS_PCT <= 0.05

# --- the trading day, IST ---
RESEARCH_AT = time(9, 0)  # pre-market research
ENTRY_START = time(9, 30)  # first 15 min only build the opening range
ENTRY_END = time(14, 30)  # no fresh entries after this
SQUARE_OFF = time(15, 15)  # everything flat before broker auto square-off (~15:20)

# --- strategy ---
ATR_SL = 1.2  # stop = entry -/+ ATR_SL x ATR(14) on the index
T1_R, T2_R = 1.5, 3.0  # targets as multiples of risk
BREAKOUT_BARS = 6  # break of the last 30 min high/low
ITM_STEPS = 1  # 1 strike in-the-money: higher delta, less theta than OTM
DELTA = 0.6  # assumed option delta for sizing  # ponytail: fixed; read broker Greeks if sizing drifts
POLL_SEC = 5  # trade manager price check interval


def costs(turnover: float) -> float:
    """Round-trip charges in Rs for an options buy+sell (rates from 1 Apr 2026): brokerage 2x20 + GST,
    STT 0.15% of the sell side, NSE 0.03553% + GST, stamp 0.003% of the buy side.
    Rs 10k in and out (turnover 20k) -> ~Rs 71."""
    return 47.2 + 0.0012 * turnover
