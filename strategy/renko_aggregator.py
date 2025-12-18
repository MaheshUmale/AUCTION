# =========================
# FILE: renko_aggregator.py
# =========================

from trading_core.models import Tick, Candle
from typing import List, Optional, Callable
import numpy as np

class RenkoAggregator:
    def __init__(self, on_renko_brick: Callable, brick_size_mode: str = 'atr', brick_size_value: float = 2.0):
        self.on_renko_brick = on_renko_brick
        self.brick_size_mode = brick_size_mode
        self.brick_size_value = brick_size_value

        # 1-second bar aggregation
        self.last_tick: Optional[Tick] = None
        self.current_1s_bar: Optional[dict] = None

        # ATR Calculation
        self.atr_period = 14
        self.atr_smoothing = 14
        self.true_ranges: List[float] = []
        self.atr: Optional[float] = None

        # Renko Calculation
        self.bricks: List[Candle] = []
        self.last_brick_price: Optional[float] = None

    def on_tick(self, tick: Tick):
        if self.last_tick is None:
            self.last_tick = tick

        # Aggregate ticks into 1-second bars
        tick_ts_sec = tick.ts // 1000
        last_tick_ts_sec = self.last_tick.ts // 1000

        if tick_ts_sec > last_tick_ts_sec:
            if self.current_1s_bar:
                self._finalize_1s_bar(last_tick_ts_sec)
            self.current_1s_bar = {
                "open": tick.ltp, "high": tick.ltp, "low": tick.ltp, "close": tick.ltp, "volume": 0
            }
        else:
            if self.current_1s_bar:
                self.current_1s_bar["high"] = max(self.current_1s_bar["high"], tick.ltp)
                self.current_1s_bar["low"] = min(self.current_1s_bar["low"], tick.ltp)
                self.current_1s_bar["close"] = tick.ltp

        self.last_tick = tick

    def _finalize_1s_bar(self, ts_sec: int):
        bar = self.current_1s_bar
        # Update ATR
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        prev_close = self.bricks[-1].close if self.bricks else close

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        self.true_ranges.append(tr)
        if len(self.true_ranges) > self.atr_period:
            self.true_ranges.pop(0)

        if len(self.true_ranges) == self.atr_period:
            if self.atr is None:
                self.atr = np.mean(self.true_ranges)
            else:
                self.atr = (self.atr * (self.atr_smoothing - 1) + tr) / self.atr_smoothing

        # Update Renko
        self._update_renko(close, ts_sec)
        self.current_1s_bar = None

    def _get_brick_size(self, close: float) -> float:
        if self.brick_size_mode == 'fixed':
            return self.brick_size_value
        elif self.brick_size_mode == 'percentage':
            return close * (self.brick_size_value / 100)
        elif self.brick_size_mode == 'atr':
            return self.atr * self.brick_size_value if self.atr else self.brick_size_value
        return self.brick_size_value

    def _update_renko(self, close: float, ts_sec: int):
        if self.last_brick_price is None:
            self.last_brick_price = close

        brick_size = self._get_brick_size(close)
        price_diff = close - self.last_brick_price

        num_bricks = int(abs(price_diff) // brick_size)

        if num_bricks == 0:
            return

        brick_direction = 1 if price_diff > 0 else -1

        for i in range(num_bricks):
            open_price = self.last_brick_price + (i * brick_size * brick_direction)
            close_price = open_price + (brick_size * brick_direction)

            brick = Candle(
                symbol=self.last_tick.symbol,
                open=open_price,
                high=max(open_price, close_price),
                low=min(open_price, close_price),
                close=close_price,
                volume=0,  # Renko bricks don't have volume
                ts=ts_sec * 1000
            )
            self.bricks.append(brick)
            self.on_renko_brick(brick)

        self.last_brick_price += num_bricks * brick_size * brick_direction
