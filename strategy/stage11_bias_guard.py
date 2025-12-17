# ============================
# stage11_bias_guard.py
# ============================

from collections import defaultdict
from typing import Dict


class TradeBiasGuard:
    """
    Concrete bias correction.
    Suppresses repeated losing direction per symbol.
    """

    def __init__(self, max_consecutive_losses: int = 2, cooldown_candles: int = 5):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_candles = cooldown_candles

        # symbol -> side -> loss_count
        self.loss_count: Dict[str, Dict[str, int]] = defaultdict(lambda: {"LONG": 0, "SHORT": 0})
        # symbol -> side -> last_loss_ts
        self.last_loss_ts: Dict[str, Dict[str, int]] = defaultdict(dict)

    def record_trade_exit(self, trade):
        if trade.pnl >= 0:
            self.loss_count[trade.symbol][trade.side] = 0
            return

        self.loss_count[trade.symbol][trade.side] += 1
        self.last_loss_ts[trade.symbol][trade.side] = trade.exit_ts

    def allow_trade(self, symbol: str, side: str, candle_ts: int) -> bool:
        if self.loss_count[symbol][side] < self.max_consecutive_losses:
            return True

        last_ts = self.last_loss_ts[symbol].get(side)
        if last_ts is None:
            return True

        candles_passed = (candle_ts - last_ts) // 60000
        return candles_passed >= self.cooldown_candles
