"""4. Risk agent. Has the final say: nothing reaches the broker without passing gate() and size()."""
from datetime import datetime

import config as C
from brain import Setup


def gate(now: datetime, trades: int, streak: int, day_pnl: float, balance: float, busy: bool) -> str | None:
    """Reason no new trade is allowed right now, or None."""
    if busy:
        return "a position is already open"
    if not C.ENTRY_START <= now.time() < C.ENTRY_END:
        return "outside entry window"
    if trades >= C.MAX_TRADES:
        return f"daily cap of {C.MAX_TRADES} trades reached"
    if day_pnl <= -C.DAILY_LOSS_PCT * balance:
        return f"daily loss limit hit (Rs {day_pnl:,.0f})"
    if streak >= C.MAX_CONSEC_LOSSES:
        return f"{streak} losses in a row, done for the day"
    return None


def unit_risk(s: Setup) -> float:
    """Expected option loss per unit at the stop: delta x index risk, +10% and 50p for slippage."""
    return C.DELTA * abs(s.entry - s.sl) * 1.1 + 0.5


def size(s: Setup, prem: float, lot: int, balance: float, cash: float) -> tuple[int, str]:
    """Lots to buy (0 = rejected) so that a stop-out loses at most RISK_PCT of the balance."""
    prem_risk = unit_risk(s)
    budget = C.RISK_PCT * balance
    by_risk = int(budget // (prem_risk * lot))
    by_cash = int(min(cash, C.MAX_POSITION_PCT * balance) // (prem * lot))
    lots = min(by_risk, by_cash, C.MAX_LOTS)
    if lots < 1:
        return 0, (f"REJECT: 1 lot risks ~Rs {prem_risk * lot:,.0f} vs budget Rs {budget:,.0f}, "
                   f"costs Rs {prem * lot:,.0f} vs cash limit Rs {min(cash, C.MAX_POSITION_PCT * balance):,.0f}")
    qty = lots * lot
    gain = C.DELTA * abs(s.t1 - s.entry) * qty
    fees = C.costs(2 * prem * qty)
    if gain < 3 * fees:
        return 0, f"REJECT: T1 gain ~Rs {gain:,.0f} is under 3x costs Rs {fees:,.0f}"
    return lots, (f"APPROVED {lots} lot(s) x {lot}: max loss ~Rs {prem_risk * qty:,.0f}, "
                  f"T1 ~Rs {gain:,.0f}, T2 ~Rs {C.DELTA * abs(s.t2 - s.entry) * qty:,.0f}")
