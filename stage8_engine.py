# =========================
# FILE: stage8_engine.py
# =========================

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import threading
from persistence import MongoPersistence
from models import *
import json
from dataclasses import asdict



# ============================
# IN stage8_engine.py
# EXACT INSERTIONS ONLY
# ============================

from stage10_add_logic import Stage10AddLogic

# ============================
# IN stage8_engine.py
# EXACT INSERTIONS ONLY
# ============================

from stage11_bias_guard import TradeBiasGuard

from stage12_stop_normalization import Stage12Controller

from stage13_14_bias_cooldown import CooldownManager,DirectionalBiasGuard


# -------------------------
# Trade Engine
# -------------------------

class TradeEngine:
    def __init__(self):
        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        print(" STAGE 8 ENGINE INITIALIZE ")

    def has_open_trade(self, symbol: str) -> bool:
        return symbol in self.open_trades

    def get_open_trade_count(self) -> int:
        return len(self.open_trades)

    def get_open_trades_list(self) -> int:
        if self.open_trades:
            return self.open_trades
        else :
            return {}
    def get_open_trade(self, symbol)->Trade:
        self.open_trades.get('symbol')

    def enter_trade(self, trade: Trade):
        print(trade.stop_price)
        self.open_trades[trade.symbol] = trade

    # def exit_trade(self, symbol: str, price: float, ts: int, reason: str):
    def exit_trade(self, symbol: str, price: float, ts: int, reason: str,pnl:float):
        trade = self.open_trades.pop(symbol, None)
        if not trade:
            return
        trade.exit_price = price
        trade.exit_ts = ts
        trade.reason = reason
        trade.pnl


        self.closed_trades.append(trade)
        print(
            "STAGE 8 ENGINE - TRADE ENGINE -->[EXIT]",
            trade.symbol,
            trade.side,
            "ENTRY", trade.entry_price,
            "STOP", trade.stop_price,
            "EXIT", trade.exit_price
        )


# -------------------------
# Auction / Strategy Engine
# -------------------------
from stage12_stop_normalization import TradeEngine as V12TradeEngine
from stage9_context import AuctionContext
class LiveAuctionEngine:
    def __init__(self):
        self.trade_engine = TradeEngine()
        # self.V12_tradeEngine = V12TradeEngine()
        self.structure: Dict[str, List[StructureLevel]] = {}
        self.last_candle_ts: Dict[str, int] = {}
        self.persistence = MongoPersistence()
        self.open_trades = {}
        self.loadFromDb()

        self.context_filter = AuctionContext(
            lookback=10,
            tick_size=0.05
        )
        # ---- inside LiveAuctionEngine.__init__ ----
        self.add_logic = Stage10AddLogic(
            max_adds=2,
            add_threshold_pct=0.003
        )
        # ---- inside LiveAuctionEngine.__init__ ----
        self.bias_guard = TradeBiasGuard(
            max_consecutive_losses=2,
            cooldown_candles=5
        )


        self.stage12 = Stage12Controller(
                        trade_engine=self.trade_engine,
                        persistence=self.persistence
                    )
        # self.stage12 = Stage12Controller(
        #                 trade_engine=self.V12_tradeEngine,
        #                 persistence=self.persistence
        #             )

        self.directionaBias_guard = DirectionalBiasGuard(
            window=20,
            min_trades=5,
            loss_threshold=0.65
        )

        self.cooldown = CooldownManager(
            cooldown_ms=3 * 60 * 1000
        )




    def loadFromDb(self):
        print("-------- REHYDRATE --------")

        # ---- OPEN TRADES ----
        self.trade_engine.open_trades = {}

        for doc in self.persistence.load_open_trades():

            trade = Trade(
                symbol=doc["symbol"],
                side=doc["side"],
                entry_price=doc["entry_price"],
                entry_ts=doc["entry_ts"],
                exit_price=doc.get("exit_price"),
                exit_ts=doc.get("exit_ts"),
                reason=doc.get("reason"),
            )
            self.trade_engine.open_trades[trade.symbol] = trade


        for doc in self.persistence.load_closed_trades():

            trade = Trade(
                symbol=doc["symbol"],
                side=doc["side"],
                entry_price=doc["entry_price"],
                entry_ts=doc["entry_ts"],
                exit_price=doc.get("exit_price"),
                exit_ts=doc.get("exit_ts"),
                reason=doc.get("reason"),
            )
            self.trade_engine.closed_trades.append(trade)


        # ---- STRUCTURE LEVELS ----
        self.structure = {}
        for doc in self.persistence.load_levels_forAll():
            lvl = StructureLevel(
                symbol=doc["symbol"],
                price=doc["price"],
                side=doc["side"],
                created_ts=doc["created_ts"],
                last_used_ts=doc.get("last_used_ts")
            )
            self.structure.setdefault(lvl.symbol, []).append(lvl)

    # -------- ticks --------

    # def on_tick(self, tick: Tick):
        # ticks only manage exits

        # self.stage12.on_tick(
        #         symbol=tick.symbol,
        #         ltp=tick.ltp,
        #         ts=tick.ts
        #     )
    def on_tick(self, tick: Tick):
        if not self.trade_engine.has_open_trade(tick.symbol):
            return

        trade = self.trade_engine.open_trades[tick.symbol]
        # print(trade)
        exit_signal = self.stage12.evaluate_exit(
            trade=trade,
            ltp=tick.ltp

        )

        if exit_signal is None:
            return

        reason, exit_price = exit_signal
        trade.exit_price = exit_price
        trade.reason = reason
        trade.exit_ts = tick.ts
        trade.status="CLOSED"
        trade.pnl = trade.exit_price - trade.entry_price if trade.side=="LONG" else trade.entry_price-trade.exit_price
        # -------- EXECUTE EXIT (ONLY PLACE) --------
        self.trade_engine.exit_trade(
            tick.symbol,
            exit_price,
            tick.ts,
            reason,
            trade.pnl
        )

        self.persistence.close_trade(
            tick.symbol,
            exit_price,
            tick.ts,
            reason,
            pnl=trade.pnl
        )

        # -------- POST EXIT SIDE EFFECTS --------
        self.directionaBias_guard.record_trade_exit(trade)

        if reason == "SL":
            self.cooldown.record_stop(tick.symbol, tick.ts)

        self.add_logic.reset(tick.symbol)



    def _allow_entry(self, candle, side: str) -> bool:
        # Stage-13: Bias filter
        if not self.directionaBias_guard.allow_trade(candle.symbol, side):
            return False

        # Stage-14: Cooldown filter
        if self.cooldown.in_cooldown(candle.symbol, candle.ts):
            return False

        return True


    def _on_trade_closed(self, trade, ts: int):
        # Record bias stats
        self.bias_guard.record_trade_exit(trade)

        # Cooldown only on SL-like exits
        if trade.reason in ("SL", "VOL_STOP"):
            self.cooldown.record_stop(trade.symbol, ts)

    # -------- candle close --------

    def on_candle_close(self, candle: Candle):
        self.stage12.on_candle_close(candle)
        self.last_candle_ts[candle.symbol] = candle.ts

        last_ts = self.persistence.get_last_candle_ts(candle.symbol)
        if last_ts is not None and candle.ts <= last_ts:
            return  # already processed
        self.persistence.update_last_candle_ts(candle.symbol, candle.ts)

        if self.trade_engine.has_open_trade(candle.symbol):
            return

        # ============================
        # AUCTION-THEORY ENTRY LOGIC
        # ============================

        # Determine trade side based on auction context
        if self.context_filter.allow_trade(candle, "LONG"):
            side = "LONG"
        elif self.context_filter.allow_trade(candle, "SHORT"):
            side = "SHORT"
        else:
            return

        # Check bias guards and cooldowns
        if not self.bias_guard.allow_trade(candle.symbol, side, candle.ts) or \
           not self.directionaBias_guard.allow_trade(candle.symbol, side) or \
           not self._allow_entry(candle, side):
            return

        # Get ATR for stop placement
        last_atr = self.stage12.atr_tracker.get_atr(candle.symbol)
        if last_atr is None:
            return  # Do not trade until ATR is ready

        # Execute trade
        stop_price = self.stage12.stop_normalizer.compute_initial_stop(candle.close, side, last_atr)
        trade = Trade(
            symbol=candle.symbol,
            side=side,
            entry_price=candle.close,
            entry_ts=candle.ts,
            stop_price=stop_price
        )

        self.stage12.on_trade_entry(trade, last_atr)
        self.persistence.save_open_trade(trade)


        # ============================
        # ADD-ONLY LOGIC (AFTER ENTRY)
        # ============================

        trade = self.trade_engine.get_open_trade(candle.symbol)
        if trade:
            if self.add_logic.can_add(trade, candle):
                self.trade_engine.add_to_trade(
                    trade,
                    price=candle.close,
                    ts=candle.ts
                )
                self.persistence.update_open_trade(trade)
                self.add_logic.register_add(candle.symbol)




# -------------------------
# Market Router (Upstox WSS)
# -------------------------

class LiveMarketRouter:
    def __init__(self, engine: LiveAuctionEngine):
        self.engine = engine

    def _extract_ltp_ts(self, ff: dict):
        """
        Returns (ltp, ts) or (None, None) if not available
        """



        # INDEX
        if "indexFF" in ff:
            ltpc = ff["indexFF"].get("ltpc")
        # EQUITY / FO
        elif "marketFF" in ff:
            ltpc = ff["marketFF"].get("ltpc")
        else:
            return None, None

        if not ltpc:
            return None, None

        ltp = ltpc.get("ltp")
        ltt = ltpc.get("ltt")

        if ltp is None or ltt is None:
            return None, None

        return float(ltp), int(ltt)


    def on_message(self, data: dict):
        feeds = data.get("feeds", {})
        current_ts = int(data.get("currentTs", time.time() * 1000))

        for symbol, feed in feeds.items():
            ff = feed.get("fullFeed", {})
            market = ff.get("marketFF") or ff.get("indexFF")
            if not market:
                continue

            # ---- tick ----
            ltp, ts = self._extract_ltp_ts(ff)

            if ltp is not None:
                self.engine.on_tick(
                    Tick(symbol=symbol,
                    ltp=ltp,
                    ts=ts)
                )

            # ---- candle close from WSS snapshot ----
            if market and "marketOHLC" in market:
                ohlc_list = market.get("marketOHLC", {}).get("ohlc", [])
                for o in ohlc_list:
                    try :
                        if "interval" in o:
                            if o["interval"] == "I1":
                                candle_ts = int(o["ts"])
                                if self.engine.last_candle_ts.get(symbol) == candle_ts:
                                    continue

                                candle = Candle(
                                    symbol=symbol,
                                    open=float(o["open"]),
                                    high=float(o["high"]),
                                    low=float(o["low"]),
                                    close=float(o["close"]),
                                    volume=float(o.get("vol", 0)),
                                    ts=candle_ts,
                                )
                                self.engine.on_candle_close(candle)
                    except :
                        import traceback
                        traceback.print_exc()
                        # print(" RECEIVED ")
                        # print(data)
                        # exit(0)


# -------------------------
# Monitor
# -------------------------

class Monitor:
    def __init__(self, engine: LiveAuctionEngine):
        self.engine = engine

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        while True:
            print(
                f"[MONITOR] open_trades={self.engine.trade_engine.get_open_trade_count()} "
                f"closed_trades={len(self.engine.trade_engine.closed_trades)}"
            )
            time.sleep(5)
