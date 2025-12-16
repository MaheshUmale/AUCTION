from dataclasses import dataclass




# -------------------------
# Data Models
# -------------------------

@dataclass
class Candle:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int  # candle close timestamp (ms)


@dataclass
class Tick:
    symbol: str
    ltp: float
    ts: int  # ltt (ms)
    side=str


from dataclasses import dataclass
from typing import Optional

@dataclass
class StructureLevel:
    symbol: str            # <-- REQUIRED, missing earlier
    price: float
    side: str              # "LONG" or "SHORT"
    created_ts: int
    last_used_ts: Optional[int] = None


# @dataclass
# class Trade:
#     symbol: str
#     side: str
#     entry_price: float
#     entry_ts: int
#     exit_price: Optional[float] = None
#     exit_ts: Optional[int] = None
#     reason: Optional[str] = None
#     pnl :Optional[float] = None
#     status : Optional[str] = "Unknown"
@dataclass
class Trade:
    symbol: str
    side: str
    entry_price: float
    entry_ts: int
    stop_price: float        #Optional[float] = None
    exit_price: float | None = None
    exit_ts: int | None = None
    reason: str | None = None
    pnl: float | None = None
    status : Optional[str] = "OPEN"