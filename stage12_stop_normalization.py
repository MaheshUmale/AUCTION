# stage12_stop_normalization.py
# Stage-12: Stop distance normalization (volatility-aware exits)
# Concrete, production-ready, no conceptual placeholders

from dataclasses import dataclass
from typing import Dict, Optional
import math
from models import Candle,Tick,Trade
 

from typing import Optional, Tuple

# =========================
# VOLATILITY TRACKER
# =========================

class ATRTracker:
    """
    Rolling ATR (Wilder-style, simplified).
    Maintains per-symbol ATR using 1-minute candles.
    """

    def __init__(self, period: int = 14):
        self.period = period
        self.tr_values: Dict[str, float] = {}
        self.atr: Dict[str, float] = {}
        self.prev_close: Dict[str, float] = {}
        self.count: Dict[str, int] = {}

    def update(self, candle: Candle) -> float:
        sym = candle.symbol

        if sym not in self.prev_close:
            tr = candle.high - candle.low
        else:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - self.prev_close[sym]),
                abs(candle.low - self.prev_close[sym]),
            )

        self.prev_close[sym] = candle.close

        if sym not in self.atr:
            # bootstrap
            self.tr_values[sym] = tr
            self.count[sym] = 1
            self.atr[sym] = tr
            return self.atr[sym]

        if self.count[sym] < self.period:
            # warm-up average
            self.tr_values[sym] += tr
            self.count[sym] += 1
            self.atr[sym] = self.tr_values[sym] / self.count[sym]
        else:
            # Wilder smoothing
            self.atr[sym] = (
                (self.atr[sym] * (self.period - 1)) + tr
            ) / self.period

        return self.atr[sym]

    def get_atr(self, symbol: str) -> Optional[float]:
        return self.atr.get(symbol)


# =========================
# STOP NORMALIZER (STAGE-12)
# =========================

class StopDistanceNormalizer:
    """
    Converts structure-based stop into volatility-aware stop.
    Prevents spike-stop-outs on valid entries.
    """

    def __init__(
        self,
        atr_mult: float = 2.0,         # INCREASED to 2.0 for breathing room
        min_stop_pct: float = 0.003,   # 0.3%
        max_stop_pct: float = 0.05,    # INCREASED to 5.0% to allow ATR to work
        tick_size: float = 0.05,
    ):
        self.atr_mult = atr_mult
        self.min_stop_pct = min_stop_pct
        self.max_stop_pct = max_stop_pct
        self.tick_size = tick_size

    def _round_price(self, price: float) -> float:
        return round(price / self.tick_size) * self.tick_size

    def compute_initial_stop(
        self,
        entry_price:float,
        side:str,
        atr: float
    ) -> float:
        # ATR-based distance
        atr_dist = atr * self.atr_mult

        # Clamp via percent bounds
        min_dist = entry_price * self.min_stop_pct
        max_dist = entry_price * self.max_stop_pct
        dist = max(min_dist, min(atr_dist, max_dist))

        if side == "LONG":
            stop = entry_price - dist
        else:
            stop = entry_price + dist
            
        return self._round_price(stop)

    def compute_take_profit(
        self,
        entry_price: float,
        stop_price: float,
        side: str
    ) -> float:
        # Open-ended trends preferred now. 
        # But we still set a "TP" as a fail-safe or R:R target?
        # Let's widen target to 3R to allow Chandelier Trail to do the work.
        risk = abs(entry_price - stop_price)
        reward = risk * 3.0  # WIDENED TARGET to 3R
        
        if side == "LONG":
            return self._round_price(entry_price + reward)
        else:
            return self._round_price(entry_price - reward)

    def evaluate_exit(
        self,
        trade:Trade,
        ltp:float
    ) -> Optional[Tuple[str, float]]:
        # STOP LOSS
        if trade.side == "LONG" and ltp <= trade.stop_price:
            return ("SL", ltp)
        
        if trade.side == "SHORT" and ltp >= trade.stop_price:
            return ("SL", ltp)

        # TAKE PROFIT
        if trade.tp_price:
            if trade.side == "LONG" and ltp >= trade.tp_price:
                return ("TP", ltp)
            if trade.side == "SHORT" and ltp <= trade.tp_price:
                return ("TP", ltp)

        return None


# =========================
# TRADE ENGINE (HARDENED)
# =========================

class TradeEngine:
    def __init__(self):
        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: Dict[int, Trade] = {}
        print(" STAGE 12 trade engine initialized ")

    def has_open_trade(self, symbol: str) -> bool:
        return symbol in self.open_trades

    def enter_trade(self, trade: Trade):
        self.open_trades[trade.symbol] = trade

    def get_open_trade(self, symbol: str) -> Optional[Trade]:
        return self.open_trades.get(symbol)

    def exit_trade(self, symbol: str, price: float, ts: int, reason: str, pnl: float = 0.0):
        trade = self.open_trades.pop(symbol, None)
        if not trade:
            return
        trade.exit_price = price
        trade.exit_ts = ts
        trade.reason = reason
        self.closed_trades[ts] = trade
        # pnl passed from stage8
        print(
            "STAGE 12 Trade Engine --[EXIT]",
            trade.symbol,
            trade.side,
            "ENTRY", trade.entry_price,
            "STOP", trade.stop_price,
            "EXIT", trade.exit_price,
            "PnL", pnl
        )
 
# =========================
# STAGE-12 INTEGRATION
# =========================

# =========================
# VOLUME TRACKER
# =========================
class VolumeTracker:
    def __init__(self, period: int = 50):
        self.period = period
        self.volumes: list = []
        self.avg_vol: float = 0.0

    def update(self, vol: float) -> float:
        self.volumes.append(vol)
        if len(self.volumes) > self.period:
            self.volumes.pop(0)
        
        self.avg_vol = sum(self.volumes) / len(self.volumes) if self.volumes else 0.0
        return self.avg_vol

    def is_spike(self, vol: float, mult: float = 4.0) -> bool:
        if self.avg_vol == 0: return False
        return vol > (self.avg_vol * mult)


class Stage12Controller:
    def __init__(self, trade_engine, persistence):
        self.atr_tracker = ATRTracker(period=14)
        self.vol_tracker = VolumeTracker(period=50) # Track Volume for Spikes
        self.stop_normalizer = StopDistanceNormalizer(
            atr_mult=2.0, 
            min_stop_pct=0.003,
            max_stop_pct=0.05,
            tick_size=0.05,
        )
        self.trade_engine = trade_engine
        self.persistence = persistence

    def on_candle_close(self, candle: Candle):
        atr = self.atr_tracker.update(candle)
        avg_vol = self.vol_tracker.update(candle.volume)
        
        # Check for Open Trade to Manage
        trade = self.trade_engine.get_open_trade(candle.symbol)
        if not trade:
            return

        # --- VOLUME SPIKE MANAGEMENT ---
        # "any event like 4x volume... time to tighten out stop"
        if self.vol_tracker.is_spike(candle.volume, mult=4.0):
            print(f"STAGE 12: Volume Spike Detected for {candle.symbol} ({candle.volume} vs {avg_vol:.0f}). Tightening Stop.")
            if trade.side == "LONG":
                # Tighten to Low of this spike bar
                # But ensure we don't LOOSEN it if current stop is higher
                new_stop = max(trade.stop_price, candle.low)
                if new_stop != trade.stop_price:
                    trade.stop_price = new_stop
                    self.persistence.save_open_trade(trade)
            else:
                # Tighten to High of this spike bar
                new_stop = min(trade.stop_price, candle.high)
                if new_stop != trade.stop_price:
                    trade.stop_price = new_stop
                    self.persistence.save_open_trade(trade)

    def on_trade_entry(self, trade: Trade, last_atr: float):
        self.trade_engine.enter_trade(trade)
        self.persistence.save_open_trade(trade)
        
    def update_initial_stop_igniting(self, trade: Trade, candle: Candle):
        """
        Called by Engine if Entry was "Igniting".
        Sets strict stop at opposite end of signal candle.
        """
        if trade.side == "LONG":
            trade.stop_price = candle.low - 0.05
        else:
            trade.stop_price = candle.high + 0.05
        
        self.persistence.save_open_trade(trade)
        # print("Ignoring Normalizer - Set IGNITING STOP")

    def evaluate_exit(self, trade: Trade, ltp: float):
        return self.stop_normalizer.evaluate_exit(trade, ltp)

    def check_trailing_stop(self, trade: Trade, ltp: float, multiplier: float = 3.0):
        """
        ATR Chandelier Trailing.
        
        Args:
            multiplier: ATR multiplier for trail buffer.
                       - 3.0 = Normal (choppy conditions)
                       - 4.0-5.0 = Trending (hold longer)
        """
        # 1. Check if we are in profit
        pct_profit = 0
        entry = trade.entry_price
        
        if trade.side == "LONG":
            pct_profit = (ltp - entry) / entry
        else:
            pct_profit = (entry - ltp) / entry

        # Threshold to start trailing - LOWERED to 0.25% as requested
        # "entry long 4985 --went till 5002 (0.34%)... SL hit at 4975"
        # 0.25% allows securing breakeven earlier.
        if pct_profit < 0.0025:
            return

        atr_tracker = self.atr_tracker
        atr = atr_tracker.get_atr(trade.symbol)
        if not atr:
            return

        # Chandelier Exit Width (dynamic multiplier)
        trail_buffer = atr * multiplier
        
        if trade.side == "LONG":
            new_stop = ltp - trail_buffer
            # Only move UP (Lock in profits, never widen risk)
            if new_stop > trade.stop_price:
                trade.stop_price = new_stop
                self.persistence.save_open_trade(trade)
                
        elif trade.side == "SHORT":
            new_stop = ltp + trail_buffer
            # Only move DOWN
            if new_stop < trade.stop_price:
                trade.stop_price = new_stop
                self.persistence.save_open_trade(trade)

    # def on_tick(self, symbol: str, ltp: float, ts: int):
    #     trade = self.trade_engine.get_open_trade(symbol)
    #     if not trade:
    #         return

    #     if self.stop_normalizer.should_exit(trade, ltp):
    #         # # guard timestamp
            # if ts < trade.entry_ts:
            #     ts = trade.entry_ts

            # self.trade_engine.exit_trade(
            #     symbol=symbol,
            #     price=ltp,
            #     ts=ts,
            #     reason="VOL_STOP"
            # )
            # self.persistence.close_trade(
            #     symbol, ltp, ts, "VOL_STOP"
            # )


