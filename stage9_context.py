from collections import deque
from typing import Dict, Deque


class Stage9ContextFilter:
    """
    Simple, concrete, stateful context filter.

    Tracks recent candle direction per symbol.
    Allows trades only in the dominant realized direction.
    """

    def __init__(self, lookback: int = 5, min_alignment: int = 3):
        self.lookback = lookback
        self.min_alignment = min_alignment

        # symbol -> deque["UP" | "DOWN"]
        self.recent_dirs: Dict[str, Deque[str]] = {}

    def update_from_candle(self, candle):
        """
        Must be called ON EVERY candle close before entry logic.
        """
        if candle.close > candle.open:
            direction = "UP"
        elif candle.close < candle.open:
            direction = "DOWN"
        else:
            return  # do nothing on doji

        dq = self.recent_dirs.setdefault(
            candle.symbol, deque(maxlen=self.lookback)
        )
        dq.append(direction)

    def allow_trade(self, symbol: str, side: str) -> bool:
        """
        side: 'LONG' or 'SHORT'
        """
        dq = self.recent_dirs.get(symbol)
        if not dq or len(dq) < self.min_alignment:
            return False  # insufficient context

        up = dq.count("UP")
        down = dq.count("DOWN")

        if side == "LONG":
            return up >= self.min_alignment and up > down

        if side == "SHORT":
            return down >= self.min_alignment and down > up

        return False
