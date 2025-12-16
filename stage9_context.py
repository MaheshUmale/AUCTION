from collections import deque
from typing import Dict, Deque, List, Optional
from auction_theory import VolumeProfile

class AuctionContext:
    """
    Determines market context using a rolling volume profile.
    Identifies if the market is trending, rotating, or balanced.
    Provides trade signals based on price interaction with the Value Area.
    """

    def __init__(
        self,
        lookback: int = 10,
        tick_size: float = 0.05,
        value_area_pct: float = 0.70
    ):
        self.lookback = lookback
        self.tick_size = tick_size
        self.value_area_pct = value_area_pct
        self.candles: Dict[str, Deque[dict]] = {}

    def _update_candles(self, candle):
        """Maintains a rolling window of recent candles."""
        if candle.symbol not in self.candles:
            self.candles[candle.symbol] = deque(maxlen=self.lookback)
        self.candles[candle.symbol].append({
            "low": candle.low,
            "high": candle.high,
            "volume": candle.volume
        })

    def _get_volume_profile(self, symbol: str) -> Optional[VolumeProfile]:
        """Returns a VolumeProfile for the current candle window."""
        if symbol not in self.candles or len(self.candles[symbol]) < self.lookback:
            return None
        return VolumeProfile(
            candles=list(self.candles[symbol]),
            tick_size=self.tick_size,
            value_area_pct=self.value_area_pct
        )

    def allow_trade(self, candle, side: str) -> bool:
        """
        Determin-es if a trade is allowed based on auction theory principles.
        - LONG trades are favored when the price is near the Value Area Low (VAL).
        - SHORT trades are favored when the price is near the Value Area High (VAH).
        """
        self._update_candles(candle)

        candle_count = len(self.candles[candle.symbol])
        if candle_count < self.lookback:
            return False

        vp = self._get_volume_profile(candle.symbol)

        if not vp or not vp.vah or not vp.val:
            return False

        vah_proximity_threshold = (vp.vah - vp.val) * 0.50
        val_proximity_threshold = (vp.vah - vp.val) * 0.50

        if side == "LONG":
            return candle.close <= (vp.val + val_proximity_threshold)

        if side == "SHORT":
            return candle.close >= (vp.vah - vah_proximity_threshold)

        return False
