import os


class Paper:
    """Paper trading: real prices and real balance from `real`, orders filled in memory at last
    price plus slippage. Stop orders are accepted but never fire (the bot manages exits itself)."""

    SLIP = 0.003

    def __init__(self, real):
        self.real, self.orders = real, {}
        self.cash = float(os.getenv("PAPER_CAPITAL") or real.funds())

    def __getattr__(self, name):  # candles, ltp, options come from the real broker
        return getattr(self.real, name)

    def funds(self) -> float:
        return self.cash

    def place(self, opt, side, qty, price, trigger=None) -> str:
        oid = f"paper-{len(self.orders) + 1}"
        st = {"status": "OPEN", "filled": 0, "avg": 0.0, "msg": "paper"}
        if trigger is None:
            px = self.real.ltp([opt.key])[opt.key] * (1 + self.SLIP if side == "BUY" else 1 - self.SLIP)
            if (px <= price) if side == "BUY" else (px >= price):
                st.update(status="COMPLETE", filled=qty, avg=round(px, 2))
                self.cash += px * qty * (-1 if side == "BUY" else 1)
        self.orders[oid] = st
        return oid

    def order(self, oid) -> dict:
        return dict(self.orders[oid])

    def cancel(self, oid) -> None:
        if self.orders[oid]["status"] == "OPEN":
            self.orders[oid]["status"] = "CANCELLED"
