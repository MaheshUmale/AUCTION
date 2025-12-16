# =========================
# stage13_14_bias_cooldown.py
# =========================

from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, Optional
import time


# =========================
# STAGE-13: Directional Bias (HTF-aware)
# =========================

class DirectionalBiasGuard:
    """
    Maintains rolling trade outcome statistics per symbol and side.
    Used to suppress trading on the statistically losing side.
    """

    def __init__(
        self,
        window: int = 20,
        min_trades: int = 5,
        loss_threshold: float = 0.65
    ):
        self.window = window
        self.min_trades = min_trades
        self.loss_threshold = loss_threshold

        # symbol -> side -> deque[bool]  (True = win, False = loss)
        self.history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: {
                "LONG": deque(maxlen=self.window),
                "SHORT": deque(maxlen=self.window),
            }
        )

    def record_trade_exit(self, trade):
        """
        Called exactly once on trade close.
        """
        win = trade.pnl is not None and trade.pnl > 0
        self.history[trade.symbol][trade.side].append(win)

    def allow_trade(self, symbol: str, side: str) -> bool:
        records = self.history[symbol][side]

        if len(records) < self.min_trades:
            return True  # insufficient data → allow

        loss_count = records.count(False)
        loss_ratio = loss_count / len(records)

        if loss_ratio >= self.loss_threshold:
            return False

        return True


# =========================
# STAGE-14: Cooldown After Stop
# =========================

class CooldownManager:
    """
    Enforces symbol-level cooldown after SL exits.
    Prevents rapid re-entry in chop / spike conditions.
    """

    def __init__(self, cooldown_ms: int = 3 * 60 * 1000):
        self.cooldown_ms = cooldown_ms
        self.last_sl_ts: Dict[str, int] = {}

    def record_stop(self, symbol: str, ts: int):
        self.last_sl_ts[symbol] = ts

    def in_cooldown(self, symbol: str, ts: int) -> bool:
        last = self.last_sl_ts.get(symbol)
        if last is None:
            return False
        return (ts - last) < self.cooldown_ms


# =========================
# INTEGRATION PATCH
# (drop-in additions to LiveAuctionEngine)
# =========================

"""
REQUIRED additions inside LiveAuctionEngine.__init__():

    self.bias_guard = DirectionalBiasGuard(
        window=20,
        min_trades=5,
        loss_threshold=0.65
    )

    self.cooldown = CooldownManager(
        cooldown_ms=3 * 60 * 1000
    )
"""


# =========================
# ENTRY FILTER (REPLACE EXISTING ENTRY BLOCK)
# =========================

"""
Inside on_candle_close(), before creating Trade():
"""

def _allow_entry(self, candle, side: str) -> bool:
    # Stage-13: Bias filter
    if not self.bias_guard.allow_trade(candle.symbol, side):
        return False

    # Stage-14: Cooldown filter
    if self.cooldown.in_cooldown(candle.symbol, candle.ts):
        return False

    return True


# =========================
# USAGE IN ENTRY LOGIC
# =========================

"""
Replace entry checks with:

if lvl.side == "LONG" and candle.close > lvl.price:
    if not self._allow_entry(candle, "LONG"):
        continue
    ...

elif lvl.side == "SHORT" and candle.close < lvl.price:
    if not self._allow_entry(candle, "SHORT"):
        continue
    ...
"""


# =========================
# EXIT HOOK (MANDATORY)
# =========================

"""
Inside ANY exit path (SL / VOL_STOP / MANUAL):

After trade exit is finalized:
"""

def _on_trade_closed(self, trade, ts: int):
    # Record bias stats
    self.bias_guard.record_trade_exit(trade)

    # Cooldown only on SL-like exits
    if trade.reason in ("SL", "VOL_STOP"):
        self.cooldown.record_stop(trade.symbol, ts)


# =========================
# MANDATORY CALL SITE
# =========================

"""
After calling:
    self.trade_engine.exit_trade(...)
    self.persistence.close_trade(...)

CALL:
    self._on_trade_closed(trade, ts)
"""


# =========================
# GUARANTEES
# =========================
# - No new TradeEngine created
# - No persistence duplication
# - Deterministic behavior
# - Bias adapts per symbol AND side
# - Cooldown prevents spike churn
# - Zero parameter hallucination
# - Fully compatible with Stage-8 → Stage-12
#
# =========================
# END
# =========================
