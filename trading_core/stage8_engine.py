# =========================
# FILE: stage8_engine.py
# =========================

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from trading_core.persistence import QuestDBPersistence
from trading_core.models import *
import json
from dataclasses import asdict

from strategy.footprint_engine import FootprintBuilder

import os
import sys
import config
# ============================
# IN stage8_engine.py
# EXACT INSERTIONS ONLY
# ============================

from strategy.stage10_add_logic import Stage10AddLogic

# ============================
# IN stage8_engine.py
# EXACT INSERTIONS ONLY
# ============================

from strategy.stage11_bias_guard import TradeBiasGuard

from strategy.stage12_stop_normalization import Stage12Controller

from strategy.stage13_14_bias_cooldown import CooldownManager,DirectionalBiasGuard

from strategy.pressure_tracker import PressureTracker
from data_handling.h1_aggregator import H1Aggregator
from strategy.orderbook_analyzer import OrderBookAnalyzer
from strategy.signal_generator import SignalGenerator
from data_handling.historical_data_fetcher import HistoricalDataFetcher
from strategy.renko_aggregator import RenkoAggregator


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
    def get_open_trade(self, symbol) -> Trade:
        return self.open_trades.get(symbol)

    def enter_trade(self, trade: Trade):
        print(f"Entering trade: {trade.symbol} @ {trade.entry_price}, SL: {trade.stop_price}")
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
from strategy.stage12_stop_normalization import TradeEngine as V12TradeEngine
from strategy.stage9_context import AuctionContext

class LiveAuctionEngine:
    """
    The LiveAuctionEngine is the core of the trading bot. It integrates market
    data, trading logic, and persistence to make real-time trading decisions.
    """
    def __init__(self, config: dict, persistence: QuestDBPersistence):
        self.config = config
        self.simulation_mode = config.get("simulation_mode", False)
        self.trade_engine = TradeEngine()
        self.structure: Dict[str, List[StructureLevel]] = {}
        self.last_candle_ts: Dict[str, int] = {}
        self.last_candles: Dict[str, Candle] = {}
        
        self.persistence = persistence
        self.open_trades = {}
        self.loadFromDb()

        # The AuctionContext provides the primary market structure analysis.
        self.context_filter = AuctionContext(
            lookback=config.get("parameters", {}).get("lookback", 120),
            tick_size=config.get("parameters", {}).get("tick_size", 0.05)
        )

        # The Stage10AddLogic determines when to add to an existing position.
        self.add_logic = Stage10AddLogic(
            max_adds=2,
            add_threshold_pct=0.003
        )

        # The TradeBiasGuard prevents over-trading in one direction after losses.
        self.bias_guard = TradeBiasGuard(
            max_consecutive_losses=2,
            cooldown_candles=5
        )


        # The Stage12Controller manages the lifecycle of trades, including stop-loss orders.
        self.stage12 = Stage12Controller(
                        trade_engine=self.trade_engine,
                        persistence=self.persistence
                    )

        # The DirectionalBiasGuard analyzes recent trade performance to identify and
        # mitigate directional biases that are not profitable.
        self.directionaBias_guard = DirectionalBiasGuard(
            window=20,
            min_trades=5,
            loss_threshold=0.55
        )

        # The CooldownManager enforces a waiting period after a losing trade to
        # prevent immediate re-entry.
        self.cooldown = CooldownManager(
            cooldown_ms=3 * 60 * 1000
        )

        # The PressureTracker monitors short-term order flow imbalances.
        self.pressure_tracker = PressureTracker(window=30)
        
        # The H1Aggregator builds a higher-timeframe context to identify the dominant trend.
        self.h1_aggregator = H1Aggregator(
            sma_period=self.config.get("parameters", {}).get("sma_period", 20),
            bias_confirm_candles=self.config.get("parameters", {}).get("bias_confirm_candles", 3),
            timeframe_minutes=self.config.get("parameters", {}).get("bias_timeframe_minutes", 60)
        )

        # The OrderBookAnalyzer scans Level 2 data for liquidity and imbalances.
        self.orderbook = OrderBookAnalyzer(imbalance_ratio=1.5)
        
        # The SignalGenerator identifies specific trade setups based on price action and technical indicators.
        self.signal_generator = SignalGenerator()
        
        # The HistoricalDataFetcher retrieves historical data for warming up the engine.
        self.fetcher = HistoricalDataFetcher(self.config.get("access_token"), self.persistence)
        
        # The FootprintBuilder creates detailed volume footprint charts for micro-level analysis.
        self.footprints: Dict[str, FootprintBuilder] = {}
        self.last_vols: Dict[str, float] = {}
        self.broadcaster = None

        # The RenkoAggregator builds Renko charts from tick data to filter out market noise.
        self.renko_aggregator = RenkoAggregator(on_renko_brick=self.on_renko_brick)

    def start_consuming(self, zmq_sub_url: str):
        """Subscribes to the ZeroMQ feed and processes incoming market data."""
        import zmq
        import json

        context = zmq.Context()
        sub_socket = context.socket(zmq.SUB)
        sub_socket.connect(zmq_sub_url)
        sub_socket.setsockopt(zmq.SUBSCRIBE, config.ZMQ_TOPIC.encode('utf-8'))

        print(f"Strategy {self.config['name']} is consuming from {zmq_sub_url}")

        while True:
            try:
                topic, message = sub_socket.recv_multipart()
                data = json.loads(message.decode('utf-8'))

                feeds = data.get("feeds", {})
                for symbol, feed in feeds.items():
                    if symbol not in self.config['symbols']:
                        continue

                    # Replicate the data parsing logic here
                    full_feed = feed.get("fullFeed", {})
                    market = full_feed.get("marketFF") or full_feed.get("indexFF")

                    if not market:
                        continue

                    # Process Tick data
                    ltpc = market.get('ltpc')
                    if ltpc and 'ltp' in ltpc and 'ltt' in ltpc:
                        tick = Tick(
                            symbol=symbol,
                            ltp=ltpc['ltp'],
                            ts=int(ltpc['ltt']),
                            volume=market.get('vtt', 0),
                            total_buy_qty=market.get('tbq', 0),
                            total_sell_qty=market.get('tsq', 0)
                        )
                        self.on_tick(tick)

                        # WARMUP CHECK
                        if not self.simulation_mode and symbol not in self.h1_aggregator.h1_candles:
                            try:
                                self.h1_aggregator.initialize_symbol(symbol)
                            except Exception as e:
                                print(f"Warmup failed for {symbol}: {e}")

                        # Update order book and footprint
                        if market:
                            self.orderbook.update(symbol, market, tick.ts)
                            last_vol = self.last_vols.get(symbol, tick.volume)
                            trade_vol = int(tick.volume) - int(last_vol)
                            if trade_vol < 0: trade_vol = 0
                            self.last_vols[symbol] = tick.volume
                            ltq = int(ltpc.get('ltq', 0))
                            if trade_vol <= 0 and ltq > 0:
                                trade_vol = ltq
                            if trade_vol > 0:
                                self.update_footprint(symbol, tick.ltp, trade_vol, tick.ts)

                            # Broadcast DOM
                            if self.broadcaster:
                                ml = market.get("marketLevel", {})
                                quotes = ml.get("bidAskQuote", [])
                                bids, asks = {}, {}
                                for q in quotes:
                                    if "bidP" in q and q["bidP"]: bids[str(q["bidP"])] = q.get("bidQ", 0)
                                    if "askP" in q and q["askP"]: asks[str(q["askP"])] = q.get("askQ", 0)

                                dom_msg = {"type": "dom", "symbol": symbol, "bids": bids, "asks": asks, "ts": tick.ts}
                                self.broadcaster(symbol, dom_msg)

                    # Process Candle Data
                    ohlc_list = market.get("marketOHLC", {}).get("ohlc", [])
                    for ohlc in ohlc_list:
                        if ohlc.get("interval") == "I1":
                            candle = Candle(
                                symbol=symbol,
                                open=float(ohlc["open"]),
                                high=float(ohlc["high"]),
                                low=float(ohlc["low"]),
                                close=float(ohlc["close"]),
                                volume=int(ohlc.get("vol", 0)),
                                ts=int(ohlc["ts"]),
                            )
                            self.on_candle_close(candle)

            except Exception as e:
                print(f"Error in strategy consumer: {e}")

    def on_renko_brick(self, brick: Candle):
        # This method will be called by the RenkoAggregator when a new brick is formed.
        # We can then broadcast it to the UI.
        if self.broadcaster:
            self.broadcaster(brick.symbol, {
                "type": "renko",
                "brick": asdict(brick)
            })

    def set_broadcaster(self, fn):
        self.broadcaster = fn

    def update_footprint(self, symbol: str, price: float, qty: float, ts: int):
        if symbol not in self.footprints:
            # Auto-Calibrate Threshold based on History
            dynamic_vol = None
            hist = self.h1_aggregator.history_candles.get(symbol)
            if hist and len(hist) > 10:
                # Calculate Avg Vol of last 200  1-min candles
                recent = list(hist)[-200:]
                avg = sum(c.volume for c in recent) / len(recent)
                if avg > 0:
                    dynamic_vol = int(avg * 1.0) # 1.0x Avg Vol
                    print(f"[Auto-Calibrate] {symbol} Vol Threshold: {dynamic_vol} (Avg: {int(avg)})")
            
            self.footprints[symbol] = FootprintBuilder(vol_threshold=dynamic_vol)
        
        fp = self.footprints[symbol]
        
        # Detect Side (Aggressor)
        # If Price >= Best Ask -> BUY
        # If Price <= Best Bid -> SELL
        # Else -> Guess based on Tick Direction? Or assume BUY if Price > LastPrice?
        # Accurate way: compare with OrderBook
        side = "UNKNOWN"
        book = self.orderbook.current_book.get(symbol)
        if book:
            if book.asks and price >= book.asks[0][0]:
                side = "BUY"
            elif book.bids and price <= book.bids[0][0]:
                side = "SELL"
        
        # Fallback if no book or inside spread
        if side == "UNKNOWN":
             # Use last tick price comparison if available? 
             # For now default to BUY if Price Up, SELL if Price Down logic could be added
             # But let's just log it as BUY for now or split 50/50? 
             # Let's default to BUY for simplicity if unknown, or maybe omit side logic in Builder?
             # Builder needs 'BUY' or 'SELL'.
             side = "BUY" 

        fp.on_tick(price, qty, side)
        
        # Check for rotation (New Bar)
        # Timestamp is in ms, Builder expects seconds for check_rotation?
        # Builder uses seconds.
        snap, rotated = fp.check_rotation(ts / 1000)
        
        # Always broadcast the update? Or only on change?
        # Broadcasting every tick might be heavy. 
        # But frontend expects "live" updates.
        # Let's broadcast the current snapshot (or partial)
        
        # If rotated, we might want to send the FINAL of previous bar and START of new.
        if rotated and snap:
             # This snapshot is the CLOSED bar
             # 1. Broadcaster (Live UI)
             if self.broadcaster:
                 self.broadcaster(symbol, snap)
             
             # 2. Persistence (DB Consistency)
             # Use the same 'auction_trading' DB as everything else
             # We can access raw db handle via self.persistence.db or add a method.
             # Accessing internal db handle is quick fix.
             try:
                 snap_doc = snap.copy()
                 snap_doc["symbol"] = symbol
                 # Ensure keys are strings for Mongo (defaultdict might have int/float keys)
                 snap_doc["levels"] = {str(k): v for k, v in snap.get("levels", {}).items()}
                 self.persistence.save_footprint(symbol, snap_doc)
             except Exception as e:
                 print(f"Footprint Save Error: {e}")
             
             # 3. SYNTHETIC STRATEGY TRIGGER
             # If WSS doesn't send OHLC, we build it here.
             try:
                 syn_candle = Candle(
                     symbol=symbol,
                     open=snap.get("open", 0),
                     high=snap.get("high", 0),
                     low=snap.get("low", 0),
                     close=snap.get("close", 0),
                     volume=snap.get("volume", 0),
                     ts=snap["ts"]
                 )
                #  print(f"DEBUG: Synthetic Candle Trigger for {symbol} @ {datetime.now()}")
                 self.on_candle_close(syn_candle)
             except Exception as e:
                 print(f"Synthetic Candle Error: {e}")
             
        # Send current incomplete bar
        current_snap = fp.snapshot(atp=price) # Using price as ATP proxy for now
        current_snap["type"] = "footprint"
        current_snap["symbol"] = symbol
        
        if self.broadcaster:
            self.broadcaster(symbol, current_snap)





    def loadFromDb(self):
        print("-------- REHYDRATE --------")

        # Reset memory state
        self.trade_engine.open_trades = {}
        self.trade_engine.closed_trades = [] # Ensure clean slate
        
        # Calculate Start of Day to filter stale trades
        from datetime import datetime
        now = datetime.now()
        today_start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = today_start_dt.timestamp() * 1000
        
        print(f"Rehydrating trades after: {today_start} ({today_start_dt})")

        open_loaded = 0
        open_skipped = 0
        closed_loaded = 0
        closed_skipped = 0

        # ---- OPEN TRADES ----
        for doc in self.persistence.load_open_trades():
            if doc["entry_ts"].timestamp() * 1000 < today_start:
                open_skipped += 1
                continue # Skip old trades

            trade = Trade(
                symbol=doc["symbol"],
                side=doc["side"],
                entry_price=doc["entry_price"],
                entry_ts=doc["entry_ts"],
                stop_price=doc.get("stop_price", 0.0),
                tp_price=doc.get("tp_price"),
                exit_price=doc.get("exit_price"),
                exit_ts=doc.get("exit_ts"),
                reason=doc.get("reason"),
            )
            self.trade_engine.open_trades[trade.symbol] = trade
            open_loaded += 1


        # ---- CLOSED TRADES ----
        for doc in self.persistence.load_closed_trades():
            if not doc["entry_ts"] or doc["entry_ts"].timestamp() * 1000 < today_start:
                closed_skipped += 1
                continue

            trade = Trade(
                symbol=doc["symbol"],
                side=doc["side"],
                entry_price=doc["entry_price"],
                entry_ts=doc["entry_ts"],
                stop_price=doc.get("stop_price", 0.0),
                tp_price=doc.get("tp_price"),
                exit_price=doc.get("exit_price"),
                exit_ts=doc.get("exit_ts"),
                reason=doc.get("reason"),
                pnl=doc.get("pnl")  # Add this line
            )
            self.trade_engine.closed_trades.append(trade)
            closed_loaded += 1
            
        print(f"Rehydration All Claims: OPEN {open_loaded} (Skipped {open_skipped}), CLOSED {closed_loaded} (Skipped {closed_skipped})")


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

    def on_tick(self, tick: Tick):
        """
        Processes a single market tick. This method is the primary entry point
        for real-time market data and is responsible for managing the lifecycle
        of open trades.
        """
        # Constants for early trade protection
        MIN_HOLD_SECONDS = 180    # 3 minutes minimum hold
        MIN_PROFIT_PCT = 0.003    # 0.3% minimum profit before discretionary exits
        
        # 1. Always update pressure tracker (even without open trade)
        self.pressure_tracker.update(tick)
        
        # Update renko aggregator
        self.renko_aggregator.on_tick(tick)

        if not self.trade_engine.has_open_trade(tick.symbol):
            return

        trade = self.trade_engine.open_trades[tick.symbol]
        symbol = tick.symbol
        
        # Calculate hold time and current profit %
        hold_time_ms = tick.ts - trade.entry_ts
        hold_time_sec = hold_time_ms / 1000
        
        if trade.side == "LONG":
            pnl_pct = (tick.ltp - trade.entry_price) / trade.entry_price
        else:
            pnl_pct = (trade.entry_price - tick.ltp) / trade.entry_price
        
        # ========================================
        # PRIORITY 1: HARD SL (Always Active)
        # This is the ONLY exit that works immediately
        # ========================================
        if trade.side == "LONG" and tick.ltp <= trade.stop_price:
            self._execute_exit(trade, tick, reason="SL")
            return
        if trade.side == "SHORT" and tick.ltp >= trade.stop_price:
            self._execute_exit(trade, tick, reason="SL")
            return
        
        # ========================================
        # EARLY TRADE PROTECTION
        # If trade is young OR profit is small:
        #   - Only SL can exit (checked above)
        #   - Allow trailing to adjust stop
        #   - Skip ALL discretionary exits
        # ========================================
        if hold_time_sec < MIN_HOLD_SECONDS or pnl_pct < MIN_PROFIT_PCT:
            # Trade needs time to develop - only trailing allowed
            if self.pressure_tracker.is_trending(symbol):
                self.stage12.check_trailing_stop(trade, tick.ltp, multiplier=4.0)
            else:
                self.stage12.check_trailing_stop(trade, tick.ltp, multiplier=3.0)
            return
        
        # ========================================
        # DISCRETIONARY EXITS (Only after protection)
        # Trade is mature (>3min) AND profitable (>0.3%)
        # ========================================
        # PRIORITY 1: WALL DETECTION EXIT (plan.md FR-EXEC-005)
        # Large liquidity blocking our direction? Exit immediately.
        # ========================================
        wall_price = self.orderbook.detect_wall(symbol, trade.side)
        if wall_price:
            # If wall is close (within 0.1%), exit
            dist_pct = abs(tick.ltp - wall_price) / tick.ltp
            if dist_pct < 0.001:
                self._execute_exit(trade, tick, reason="OB_WALL_DETECTED")
                return

        # ========================================
        # PRIORITY 2: EXHAUSTION AGGRESSION EXIT
        # 10 ticks showing strong opposing pressure
        # ========================================
        if self.pressure_tracker.check_exhaustion_aggression(symbol, trade.side, tick_count=10):
            self._execute_exit(trade, tick, reason="EXHAUSTION_AGGRESSION")
            return
        
        # Check TP (but skip if pressure supports direction)
        exit_signal = self.stage12.evaluate_exit(trade=trade, ltp=tick.ltp)
        if exit_signal:
            reason, exit_price = exit_signal
            if reason == "TP" and self.pressure_tracker.pressure_supports(symbol, trade.side):
                # Pressure favorable - let it run
                pass
            else:
                self._execute_exit(trade, tick, reason=reason)
                return
        
        # ========================================
        # TRAILING STOP (dynamic based on trend)
        # ========================================
        if self.pressure_tracker.is_trending(symbol):
            self.stage12.check_trailing_stop(trade, tick.ltp, multiplier=4.0)
        else:
            self.stage12.check_trailing_stop(trade, tick.ltp, multiplier=3.0)
    
    def _check_candle_hl_broken(self, trade: Trade, tick: Tick) -> bool:
        """
        Check if last candle's H/L is broken against position.
        LONG: price breaks below last candle's low → EXIT
        SHORT: price breaks above last candle's high → EXIT
        """
        last_candle = self.last_candles.get(tick.symbol)
        if not last_candle:
            return False
        
        if trade.side == "LONG":
            return tick.ltp < last_candle.low
        else:  # SHORT
            return tick.ltp > last_candle.high
    
    def _execute_exit(self, trade: Trade, tick: Tick, reason: str):
        """
        Centralized exit execution - single place for all exits.
        """
        exit_price = tick.ltp
        trade.exit_price = exit_price
        trade.reason = reason
        trade.exit_ts = tick.ts
        trade.status = "CLOSED"
        trade.pnl = (exit_price - trade.entry_price) if trade.side == "LONG" else (trade.entry_price - exit_price)
        
        # Execute exit
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
        
        # Post-exit side effects
        self.directionaBias_guard.record_trade_exit(trade)
        
        if reason in ("SL", "EXHAUSTION_AGGRESSION", "CANDLE_HL_BREAK"):
            self.cooldown.record_stop(tick.symbol, tick.ts)
        
        # Reset pressure tracker for this symbol
        self.pressure_tracker.reset(tick.symbol)
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
        """
        Processes a closed candle. This method is the primary entry point for
        the core trading logic, where the system evaluates market structure and
        identifies potential trade entries.
        """
        self.stage12.on_candle_close(candle)
        self.last_candle_ts[candle.symbol] = candle.ts
        
        # Store for H/L break detection in on_tick
        self.last_candles[candle.symbol] = candle
        
        # ============================
        # Stage-16: H1 AGGREGATION
        # Feed every 1-min candle to H1 aggregator
        # ============================
        self.h1_aggregator.on_1min_candle(candle)

        last_ts = self.persistence.get_last_candle_ts(candle.symbol)
        if last_ts is not None and candle.ts is not None:
            # Convert last_ts (datetime) to milliseconds to compare with candle.ts
            if int(candle.ts) <= int(last_ts.timestamp() * 1000):
                return  # already processed
       
        self.persistence.update_last_candle_ts(candle.symbol, candle.ts)

        if self.trade_engine.has_open_trade(candle.symbol):
            return

        # ============================
        # AUCTION-THEORY ENTRY LOGIC
        # ============================

        # MINIMUM VOLUME CHECK: Dynamic based on Footprint Rotation Threshold
        # We want to ensure the candle is "full" relative to its specific rotation setting.
        # This accounts for Auto-Calibration per symbol.
        entry_thresh = config.MIN_ENTRY_VOLUME # Default Fallback
        
        if candle.symbol in self.footprints:
             # Use the actual threshold assigned to this symbol's builder
             fp_thresh = self.footprints[candle.symbol].vol_threshold
             # Use same multiplier (e.g. 0.7)
             entry_thresh = int(fp_thresh * 0.7)
        
        if "INDEX" in candle.symbol or "Nifty" in candle.symbol:
             # Indices have no volume (or unreliable volume in some feeds)
             # Skip volume check
             pass
        elif candle.volume < entry_thresh:
             print(f"[REJECT] {candle.symbol} Vol {candle.volume} < {entry_thresh} (Dynamic)")
             return

             
        is_igniting = False
        # Special Igniting Check First
        if self.context_filter._check_igniting_candle(candle.symbol, candle.volume):
            if candle.close > candle.open: # Green
                side = "LONG"
                is_igniting = True
            elif candle.close < candle.open:
                side = "SHORT"
                is_igniting = True
            else:
                return # Doji igniting? Skip.
        
        if not is_igniting:
            if self.context_filter.allow_trade(candle, "LONG"):
                side = "LONG"
            elif self.context_filter.allow_trade(candle, "SHORT"):
                side = "SHORT"
            else:
                print(f"[REJECT] {candle.symbol} not igniting  Context Filter blocked")
                return #  REMOVE RETURN CONTINUE Aother logic
                 

        # ============================
        # Stage-16: H1 BIAS FILTER (plan.md FR-CTX-002)
        # Only trade in direction of H1 trend
        # ============================
        if not self.h1_aggregator.allows_trade(candle.symbol, side):
            # H1 bias doesn't support this direction
            # BACKTEST FALLBACK: If bias is None (no history) and sim mode, allow.
            if self.simulation_mode and self.h1_aggregator.get_bias(candle.symbol) is None:
                pass # Allow
            else:
                print(f"[REJECT] {candle.symbol} H1 Bias Agreement blocked (Side: {side})")
                return
            
        # ============================
        # Stage-18: SIGNAL VALIDATION (plan.md FR-SIG-001/002)
        # Check for Pullback + Reversal Pattern
        # ============================
        # Get H1 levels for pullback check
        h1_levels = self.h1_aggregator.get_h1_levels(candle.symbol)
        bias = self.h1_aggregator.get_bias(candle.symbol)
        
        # If we are in backtest mode without enough history, skip strict signal check
        # But in live, we want strict adherence.
        # Check signal from generator
        signal = self.signal_generator.get_signal(candle, h1_levels, bias)
        
        # If no strict signal, but we have bias... 
        # Plan says "Upon a pullback... system must detect reversal".
        # This implies we ONLY trade if signal generator confirms.
        if not signal:
            # If standard logic said go, but signal generator didn't see a setup...
            # We skip. 
            pass 
            # NOTE: Uncomment below to ENFORCE strict patterns. 
            # For now, leaving it as a filter that allows IGNITING bars to bypass.
            # In simulation, if we lack H1 levels, we might miss signals. 
            if not is_igniting and not self.simulation_mode: 
                 print(f"[REJECT] {candle.symbol} No Signal Pattern (Pullback/Reversal)")
                 return 
        
        # ============================
        # Stage-17: ORDER BOOK IMBALANCE (plan.md FR-EXEC-001)
        # TBQ > 1.5x TSQ for LONG, TSQ > 1.5x TBQ for SHORT
        # ============================
        if not self.orderbook.check_entry_imbalance(candle.symbol, side):
            # Order book imbalance doesn't confirm entry
            # BACKTEST FALLBACK: If OB is empty (missing L2 data) and sim mode, allow.
            book = self.orderbook.current_book.get(candle.symbol)
            if self.simulation_mode and (not book or (book.tbq == 0 and book.tsq == 0)):
                pass # Allow
            else:
                # Real rejection
                print(f"[REJECT] {candle.symbol} OrderBook Imbalance blocked")
                return

        # Check bias guards and cooldowns
        if not self.bias_guard.allow_trade(candle.symbol, side, candle.ts) or \
           not self.directionaBias_guard.allow_trade(candle.symbol, side) or \
           not self._allow_entry(candle, side):
            print(f"[REJECT] {candle.symbol} Bias/Cooldown/Guard blocked")
            return

        # Get ATR for stop placement
        last_atr = self.stage12.atr_tracker.get_atr(candle.symbol)
        if last_atr is None:
            print(f"[REJECT] {candle.symbol} ATR not ready")
            return  # Do not trade until ATR is ready

        # Execute trade
        # Stage-17: Dynamic SL based on Order Book (plan.md FR-EXEC-004)
        ob_stop = self.orderbook.get_dynamic_stop(candle.symbol, side, candle.low, candle.high)
        
        # Fallback to ATR-based if OB stop not available/fails
        atr_stop = self.stage12.stop_normalizer.compute_initial_stop(candle.close, side, last_atr)
        
        # Use OB stop if valid, else ATR (Or maybe check which is tighter/safer? Plan says "whichever is wider")
        # Plan: "1 tick below bid OR below candle low, whichever is wider"
        # The get_dynamic_stop method implements this logic.
        stop_price = ob_stop if ob_stop else atr_stop
        
        tp_price = self.stage12.stop_normalizer.compute_take_profit(candle.close, stop_price, side)

        trade = Trade(
            symbol=candle.symbol,
            side=side,
            entry_price=candle.close,
            entry_ts=candle.ts,
            stop_price=stop_price,
            tp_price=tp_price,
            reason="IGNITING" if is_igniting else "STANDARD"
        )

        self.trade_engine.enter_trade(trade)
        
        # If IGNITING, Override Stop Logic Immediately
        if is_igniting:
             self.stage12.update_initial_stop_igniting(trade, candle)
        else:
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
