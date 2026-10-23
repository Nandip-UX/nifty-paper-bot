"""Broker contract. Every adapter module exposes `Broker()` with these methods:

    funds() -> float                     cash available for new intraday option buys, in Rs
    candles(index, days) -> list[Candle] 5-minute candles of an index spot ("NIFTY", "BANKNIFTY",
                                         "FINNIFTY", "INDIAVIX") for the last `days` calendar days
                                         incl. today, oldest first, tz-aware IST candle START times
    ltp(keys) -> {key: float}            last price; key = index name above or Option.key
    options(index) -> list[Option]       every listed NFO option contract of that index
    place(opt, side, qty, price, trigger=None) -> order_id
                                         side "BUY"/"SELL", qty in units (multiple of lot),
                                         intraday product (MIS). trigger=None -> LIMIT at price,
                                         else stop-loss-limit (SL) triggering at `trigger`
    order(order_id) -> {"status": "OPEN"|"COMPLETE"|"CANCELLED"|"REJECTED",
                        "filled": int, "avg": float, "msg": str}
    cancel(order_id) -> None
"""
import importlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
Candle = tuple[datetime, float, float, float, float, float]  # start, open, high, low, close, volume


@dataclass(frozen=True)
class Option:
    key: str  # the broker's own instrument id, handed back to ltp()/place()
    symbol: str  # readable trading symbol, e.g. NIFTY25O2825000CE
    index: str  # NIFTY | BANKNIFTY | FINNIFTY
    expiry: date
    strike: float
    kind: str  # CE | PE
    lot: int


def tick(price: float) -> float:
    """Round to the NSE options tick of Rs 0.05."""
    return max(0.05, round(round(price / 0.05) * 0.05, 2))


def cached_token(name: str, fetch) -> str:
    """Today's login token for `name`; calls fetch() (the login) at most once per day."""
    path = Path(__file__).resolve().parent.parent / ".tokens.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    key = f"{name}:{date.today()}"
    if key not in data:
        data = {k: v for k, v in data.items() if not k.startswith(name + ":")}
        data[key] = fetch()
        path.write_text(json.dumps(data))
        os.chmod(path, 0o600)
    return data[key]


def connect(name: str):
    return importlib.import_module(f"brokers.{name}").Broker()
