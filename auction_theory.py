import pandas as pd
from typing import List, Optional

class VolumeProfile:
    """
    Calculates a simple volume profile from candle data.
    Provides Value Area (VA) and Point of Control (POC).
    """

    def __init__(
        self,
        candles: List[dict],
        tick_size: float = 0.05,
        value_area_pct: float = 0.70
    ):
        if not candles:
            raise ValueError("Candle list cannot be empty")

        self.candles = candles
        self.tick_size = tick_size
        self.value_area_pct = value_area_pct
        self.profile = self._calculate_profile()
        self.poc: Optional[float] = None
        self.vah: Optional[float] = None
        self.val: Optional[float] = None

        if not self.profile.empty:
            self.poc = self.profile.idxmax()
            self.vah, self.val = self._calculate_value_area()

    def _calculate_profile(self) -> pd.Series:
        """
        Creates a price-volume distribution.
        """
        min_low = min(c["low"] for c in self.candles)
        max_high = max(c["high"] for c in self.candles)

        price_levels = pd.Series(
            index=pd.RangeIndex(
                start=int(min_low / self.tick_size),
                stop=int(max_high / self.tick_size) + 1
            ) * self.tick_size,
            dtype=float
        ).fillna(0)

        for candle in self.candles:
            low = int(candle["low"] / self.tick_size) * self.tick_size
            high = int(candle["high"] / self.tick_size) * self.tick_size

            levels_in_range = price_levels.loc[low:high].index

            if not levels_in_range.empty:
                volume_per_level = candle["volume"] / len(levels_in_range)
                price_levels.loc[levels_in_range] += volume_per_level

        return price_levels

    def _calculate_value_area(self) -> (Optional[float], Optional[float]):
        """
        Finds the price range with the highest X% of volume.
        """
        if self.profile.empty or self.poc is None:
            return None, None

        total_volume = self.profile.sum()
        target_volume = total_volume * self.value_area_pct

        poc_ix = self.profile.index.get_loc(self.poc)

        upper_prices = self.profile.iloc[poc_ix:]
        lower_prices = self.profile.iloc[:poc_ix]

        value_area_volume = self.profile.at[self.poc]

        vah = self.poc
        val = self.poc

        upper_ix = poc_ix + 1
        lower_ix = poc_ix - 1

        while value_area_volume < target_volume:
            take_upper = False
            if upper_ix < len(self.profile) and lower_ix >= 0:
                take_upper = self.profile.iloc[upper_ix] > self.profile.iloc[lower_ix]
            elif upper_ix < len(self.profile):
                take_upper = True
            elif lower_ix < 0:
                break

            if take_upper:
                value_area_volume += self.profile.iloc[upper_ix]
                vah = self.profile.index[upper_ix]
                upper_ix += 1
            else:
                value_area_volume += self.profile.iloc[lower_ix]
                val = self.profile.index[lower_ix]
                lower_ix -= 1

        return vah, val

    @property
    def is_balanced(self) -> bool:
        """
        Checks if the profile is balanced (bell-shaped).
        A simple heuristic is if the POC is near the midpoint of the value area.
        """
        if not self.poc or not self.vah or not self.val:
            return False

        midpoint = self.val + (self.vah - self.val) / 2
        # Check if POC is within, say, 20% of the VA range from the midpoint
        tolerance = (self.vah - self.val) * 0.20
        return abs(self.poc - midpoint) <= tolerance

    @property
    def dominant_side(self) -> Optional[str]:
        """
        Determines if there is a buying or selling dominance.
        - 'BUYER' if POC is in the upper half of the value area.
        - 'SELLER' if POC is in the lower half of the value area.
        """
        if not self.is_balanced:
            if self.poc > self.val + (self.vah - self.val) / 2:
                return "BUYER"
            else:
                return "SELLER"
        return None
