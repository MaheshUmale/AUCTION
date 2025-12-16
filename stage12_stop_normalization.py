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
        atr_mult: float = 1.5,
        min_stop_pct: float = 0.003,   # 0.3%
        max_stop_pct: float = 0.02,    # 2.0%
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
        entry_price

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

    def should_exit(
        self,
        trade: Trade,
        ltp: float
    ) -> bool:
        if trade.side == "LONG":
            return ltp <= trade.stop_price
        else:
            return ltp >= trade.stop_price


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

    def exit_trade(self, symbol: str, price: float, ts: int, reason: str):
        trade = self.open_trades.pop(symbol, None)
        if not trade:
            return
        trade.exit_price = price
        trade.exit_ts = ts
        trade.reason = reason
        self.closed_trades[ts] = trade
        pnl = trade.exit_price -trade.entry_price if trade.side=="LONG" else trade.entry_price - trade.exit_price
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

# class Stage12Controller:
#     """
#     Drop-in for existing Stage-8/9/10/11 engine.
#     Only responsibility: volatility-aware stop placement + exit.
#     """

#     def __init__(self):
#         self.atr_tracker = ATRTracker(period=14)
#         self.stop_normalizer = StopDistanceNormalizer(
#             atr_mult=1.8,
#             min_stop_pct=0.004,
#             max_stop_pct=0.025,
#             tick_size=0.05,
#         )
#         self.trade_engine = TradeEngine()

#     # ---- CALL ON EVERY 1-MIN CANDLE CLOSE ----
#     def on_candle_close(self, candle: Candle):
#         atr = self.atr_tracker.update(candle)

#         trade = self.trade_engine.get_open_trade(candle.symbol)
#         if not trade:
#             return

#         # Time-based trailing (optional hardening)
#         if trade.side == "LONG":
#             trade.stop_price = max(trade.stop_price, candle.low - atr * 0.2)
#         else:
#             trade.stop_price = min(trade.stop_price, candle.high + atr * 0.2)

#     # ---- CALL ON ENTRY ----
#     def on_trade_entry(self, trade: Trade, last_atr: float):
#         trade.stop_price = self.stop_normalizer.compute_initial_stop(
#             trade, last_atr
#         )
#         self.trade_engine.enter_trade(trade)

#     # ---- CALL ON EVERY TICK ----
#     def on_tick(self, symbol: str, ltp: float, ts: int):
#         trade = self.trade_engine.get_open_trade(symbol)
#         if not trade:
#             return

#         if self.stop_normalizer.should_exit(trade, ltp):
#             self.trade_engine.exit_trade(
#                 symbol=symbol,
#                 price=ltp,
#                 ts=ts,
#                 reason="VOL_STOP"
#             )
class Stage12Controller:
    def __init__(self, trade_engine, persistence):
        self.atr_tracker = ATRTracker(period=14)
        self.stop_normalizer = StopDistanceNormalizer(
            atr_mult=1.8,
            min_stop_pct=0.004,
            max_stop_pct=0.025,
            tick_size=0.05,
        )
        self.trade_engine = trade_engine
        self.persistence = persistence

    def on_candle_close(self, candle: Candle):
        atr = self.atr_tracker.update(candle)

        trade = self.trade_engine.get_open_trade(candle.symbol)
        if not trade:
            return

        if trade.side == "LONG":
            trade.stop_price = max(trade.stop_price, candle.low - atr * 0.2)
        else:
            trade.stop_price = min(trade.stop_price, candle.high + atr * 0.2)

        self.persistence.save_open_trade(trade)

    def on_trade_entry(self, trade: Trade, last_atr: float):
        # trade.stop_price = self.stop_normalizer.compute_initial_stop(
        #     trade, last_atr
        # )
        self.trade_engine.enter_trade(trade)
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


    def evaluate_exit(
        self,
        trade:Trade,
        ltp:float
        
    ) -> Optional[Tuple[str, float]]:
        """
        Returns:
            None                    -> no exit
            ("SL", stop_price)      -> exit required
        """
        
 
        if trade.side == "LONG" and ltp <= trade.stop_price:
            return ("SL", ltp)

        if trade.side == "SHORT" and ltp >= trade.stop_price:
            return ("SL", ltp)

        return None

# =========================
# END OF STAGE-12
# =========================
