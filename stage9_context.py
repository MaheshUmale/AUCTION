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
        Determines if a trade is allowed based on the market regime identified
        by the volume profile.
        - In balanced markets, it favors mean-reversion trades.
        - In unbalanced markets, it favors trend-following trades.
        """
        self._update_candles(candle)

        if len(self.candles.get(candle.symbol, [])) < self.lookback:
            return False

        vp = self._get_volume_profile(candle.symbol)
        if not all([vp, vp.poc, vp.vah, vp.val]):
            return False

        # --- Regime-Based Logic ---

        # 1. Balanced Market (Mean Reversion)
        if vp.is_balanced:
            if side == "LONG" and candle.close <= vp.val:
                return True
            if side == "SHORT" and candle.close >= vp.vah:
                return True

        # 2. Unbalanced Market (Trend Following)
        else:
            dominant_side = vp.dominant_side
            if side == "LONG" and dominant_side == "BUYER" and candle.close <= vp.poc:
                # Buy on pullbacks to the POC in an uptrend
                return True
            if side == "SHORT" and dominant_side == "SELLER" and candle.close >= vp.poc:
                # Sell on rallies to the POC in a downtrend
                return True

        return False
