# ============================
# stage10_add_logic.py
# ============================

from typing import Dict


class Stage10AddLogic:
    """
    Concrete add-only logic.
    Adds ONLY if:
    - trade already open
    - trade in profit
    - price continues in trade direction
    - max adds not exceeded
    """

    def __init__(self, max_adds: int = 2, add_threshold_pct: float = 0.003):
        self.max_adds = max_adds
        self.add_threshold_pct = add_threshold_pct
        # symbol -> add_count
        self.add_count: Dict[str, int] = {}

    def reset(self, symbol: str):
        self.add_count.pop(symbol, None)

    def can_add(self, trade, candle) -> bool:
        cnt = self.add_count.get(trade.symbol, 0)
        if cnt >= self.max_adds:
            return False

        if trade.side == "LONG":
            if candle.close <= trade.entry_price:
                return False
            move_pct = (candle.close - trade.entry_price) / trade.entry_price
            return move_pct >= self.add_threshold_pct

        if trade.side == "SHORT":
            if candle.close >= trade.entry_price:
                return False
            move_pct = (trade.entry_price - candle.close) / trade.entry_price
            return move_pct >= self.add_threshold_pct

        return False

    def register_add(self, symbol: str):
        self.add_count[symbol] = self.add_count.get(symbol, 0) + 1
