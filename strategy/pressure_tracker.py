# =========================
# FILE: pressure_tracker.py
# =========================
# Stage-15: Delta/Pressure Tracker for Trend Detection
# Uses TBQ/TSQ changes over rolling window to detect trending conditions

from collections import deque
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PressureSnapshot:
    """Single point-in-time pressure reading"""
    ts: int
    tbq: int  # Total Buy Quantity
    tsq: int  # Total Sell Quantity
    ltp: float


class PressureTracker:
    """
    Tracks delta pressure from TBQ/TSQ over 20-50 ticks.
    Detects trending vs choppy conditions in real-time.
    
    Key Metrics:
    - pressure_ratio = (TBQ_delta - TSQ_delta) / total_delta
      Range: -1 (strong sellers) to +1 (strong buyers)
    - is_trending = abs(pressure_ratio) > threshold
    """

    def __init__(self, window: int = 30):
        """
        Args:
            window: Number of ticks to track (20-50 recommended)
        """
        self.window = window
        # symbol -> deque of PressureSnapshot
        self.history: Dict[str, deque] = {}
        
        # Cache last known values to detect changes
        self.last_tbq: Dict[str, int] = {}
        self.last_tsq: Dict[str, int] = {}

    def _get_history(self, symbol: str) -> deque:
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=self.window)
        return self.history[symbol]

    def update(self, tick) -> None:
        """
        Update pressure tracker with new tick data.
        
        Args:
            tick: Tick object with symbol, ts, total_buy_qty, total_sell_qty, ltp
        """
        symbol = tick.symbol
        history = self._get_history(symbol)
        
        # Only add if TBQ/TSQ actually changed (avoid duplicate snapshots)
        if symbol in self.last_tbq:
            if (tick.total_buy_qty == self.last_tbq[symbol] and 
                tick.total_sell_qty == self.last_tsq[symbol]):
                return
        
        snapshot = PressureSnapshot(
            ts=tick.ts,
            tbq=tick.total_buy_qty,
            tsq=tick.total_sell_qty,
            ltp=tick.ltp
        )
        history.append(snapshot)
        
        self.last_tbq[symbol] = tick.total_buy_qty
        self.last_tsq[symbol] = tick.total_sell_qty

    def get_pressure_ratio(self, symbol: str) -> float:
        """
        Returns pressure ratio from -1 (sellers dominant) to +1 (buyers dominant).
        
        Calculation:
        - TBQ_delta = change in Total Buy Qty over window
        - TSQ_delta = change in Total Sell Qty over window
        - ratio = (TBQ_delta - TSQ_delta) / (|TBQ_delta| + |TSQ_delta|)
        """
        history = self._get_history(symbol)
        
        if len(history) < 2:
            return 0.0
        
        first = history[0]
        last = history[-1]
        
        tbq_delta = last.tbq - first.tbq
        tsq_delta = last.tsq - first.tsq
        
        total = abs(tbq_delta) + abs(tsq_delta)
        if total == 0:
            return 0.0
        
        return (tbq_delta - tsq_delta) / total

    def is_trending(self, symbol: str, threshold: float = 0.5) -> bool:
        """
        Check if market is in trending condition.
        
        Args:
            symbol: Instrument symbol
            threshold: Min absolute pressure ratio to consider trending (default 0.5)
            
        Returns:
            True if pressure is strongly one-sided (trending)
        """
        return abs(self.get_pressure_ratio(symbol)) > threshold

    def get_trend_direction(self, symbol: str) -> Optional[str]:
        """
        Get current trend direction based on pressure.
        
        Returns:
            "UP" if buyers dominant
            "DOWN" if sellers dominant
            None if neutral/choppy
        """
        ratio = self.get_pressure_ratio(symbol)
        
        if ratio > 0.3:
            return "UP"
        elif ratio < -0.3:
            return "DOWN"
        return None

    def pressure_supports(self, symbol: str, side: str) -> bool:
        """
        Check if current pressure supports the trade direction.
        Used to decide whether to let winners run.
        
        Args:
            symbol: Instrument symbol
            side: "LONG" or "SHORT"
            
        Returns:
            True if pressure aligns with trade direction
        """
        ratio = self.get_pressure_ratio(symbol)
        
        if side == "LONG":
            return ratio > 0.2  # Buyers still dominant
        else:  # SHORT
            return ratio < -0.2  # Sellers still dominant

    def check_exhaustion_aggression(
        self, 
        symbol: str, 
        side: str, 
        tick_count: int = 10
    ) -> bool:
        """
        Check if recent ticks show strong aggression AGAINST the position.
        Used as exhaustion exit trigger.
        
        Args:
            symbol: Instrument symbol
            side: Current position side ("LONG" or "SHORT")
            tick_count: Number of recent ticks to check (default 10)
            
        Returns:
            True if opposing side is aggressively winning → EXIT signal
        """
        history = self._get_history(symbol)
        
        if len(history) < tick_count:
            return False
        
        recent = list(history)[-tick_count:]
        
        tbq_delta = recent[-1].tbq - recent[0].tbq
        tsq_delta = recent[-1].tsq - recent[0].tsq
        
        # Require significant opposing pressure (1.5x)
        if side == "LONG":
            # Sellers must be significantly stronger than buyers
            return tsq_delta > tbq_delta * 1.5 and tsq_delta > 0
        else:  # SHORT
            # Buyers must be significantly stronger than sellers
            return tbq_delta > tsq_delta * 1.5 and tbq_delta > 0

    def get_pressure_momentum(self, symbol: str) -> float:
        """
        Calculate rate of change in pressure (acceleration).
        Positive = pressure building in buyer direction
        Negative = pressure building in seller direction
        
        Returns:
            Rate of change in pressure ratio
        """
        history = self._get_history(symbol)
        
        if len(history) < 10:
            return 0.0
        
        # Compare first half vs second half
        mid = len(history) // 2
        
        first_half = list(history)[:mid]
        second_half = list(history)[mid:]
        
        # First half pressure
        tbq1 = first_half[-1].tbq - first_half[0].tbq
        tsq1 = first_half[-1].tsq - first_half[0].tsq
        total1 = abs(tbq1) + abs(tsq1)
        ratio1 = (tbq1 - tsq1) / total1 if total1 > 0 else 0
        
        # Second half pressure
        tbq2 = second_half[-1].tbq - second_half[0].tbq
        tsq2 = second_half[-1].tsq - second_half[0].tsq
        total2 = abs(tbq2) + abs(tsq2)
        ratio2 = (tbq2 - tsq2) / total2 if total2 > 0 else 0
        
        return ratio2 - ratio1

    def reset(self, symbol: str) -> None:
        """Clear history for a symbol (e.g., after trade exit)"""
        if symbol in self.history:
            self.history[symbol].clear()
        if symbol in self.last_tbq:
            del self.last_tbq[symbol]
        if symbol in self.last_tsq:
            del self.last_tsq[symbol]
