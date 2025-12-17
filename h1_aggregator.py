# =========================
# FILE: h1_aggregator.py
# =========================
# Phase 1: H1 Context Module
# Aggregates 1-min candles to H1, calculates SMA 50, determines trend bias

from collections import deque
from typing import Dict, Optional, List
from dataclasses import dataclass
import time


import config

@dataclass
class H1Candle:
    """Aggregated Generic Candle (Timeframe specific)"""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int  # Candle close timestamp (ms)


class H1Aggregator: # Kept name for compatibility, but acts as MultiFrameAggregator
    """
    Aggregates 1-minute candles into Timeframe candles.
    Calculates SMA and Trend Bias.
    """
    
    def __init__(
        self, 
        sma_period: int = config.SMA_PERIOD, 
        bias_confirm_candles: int = config.BIAS_CONFIRM_CANDLES, 
        timeframe_minutes: int = config.BIAS_TIMEFRAME_MINUTES
    ):
        self.sma_period = sma_period
        self.bias_confirm_candles = bias_confirm_candles
        self.timeframe_minutes = timeframe_minutes 
        
        # symbol -> list of 1-min candles in current window
        self.current_window: Dict[str, List[dict]] = {}
        
        # symbol -> deque of completed candles (for SMA calculation)
        self.history_candles: Dict[str, deque] = {}
        
        # symbol -> current window start timestamp
        self.window_start_ts: Dict[str, int] = {}
        
        # symbol -> current bias ("BULLISH", "BEARISH", None)
        self.bias: Dict[str, Optional[str]] = {}
        
        # symbol -> count of consecutive candles above/below SMA
        self.bias_count: Dict[str, int] = {}
        self.bias_direction: Dict[str, str] = {}
        
        # Connect to DB
        try:
            from pymongo import MongoClient
            self.client = MongoClient(config.MONGO_URI)
            self.db = self.client[config.DB_NAME]
            # Use specific collection based on timeframe
            self.collection = self.db[f"{config.H1_COLLECTION_PREFIX}{timeframe_minutes}m"]
        except:
            self.collection = None
        
        # Alias for external access compatibility
        self.h1_candles = self.history_candles

    def initialize_symbol(self, symbol: str):
        """Load historical candles for symbol to warm up SMA"""
        if self.collection is None:
            return
            
        # Determine current window start
        now_ms = int(time.time() * 1000)
        current_start = self._get_window_start(now_ms)
        
        # Load last N candles
        cursor = self.collection.find(
            {"symbol": symbol, "ts": {"$lt": current_start}},
            {"_id": 0}
        ).sort("ts", 1).limit(self.sma_period + 20)
        
        loaded = list(cursor)
        if loaded:
            self.history_candles[symbol] = deque(maxlen=self.sma_period + 10)
            for c in loaded:
                candle = H1Candle(
                    symbol=c["symbol"],
                    open=c["open"],
                    high=c["high"],
                    low=c["low"],
                    close=c["close"],
                    volume=c["volume"],
                    ts=c["ts"]
                )
                self.history_candles[symbol].append(candle)
            
            # Update initial bias
            self._update_initial_bias(symbol)
            
            print(f"[{self.timeframe_minutes}m] Loaded {len(loaded)} historical candles for {symbol}")

    def _update_initial_bias(self, symbol: str):
        """Update bias based on loaded history w/o requiring new ticks"""
        if symbol not in self.history_candles:
            return
            
        candles = list(self.history_candles[symbol])
        if len(candles) < self.sma_period:
            return
            
        last_candle = candles[-1]
        self._update_bias(symbol, last_candle)

    
    def _get_window_start(self, ts_ms: int) -> int:
        """
        Round timestamp down to the start of the timeframe window.
        Aligned to Market Open (9:15 AM IST).
        """
        # Convert to seconds
        ts_sec = ts_ms // 1000
        # IST offset (5:30 = 19800 seconds)
        ist_offset = 19800
        # Get seconds since midnight IST
        local_ts = ts_sec + ist_offset
        seconds_since_midnight = local_ts % 86400
        
        # Market opens at 9:15 AM IST = 33300 seconds
        market_open = 33300
        
        # Seconds since market open
        since_open = seconds_since_midnight - market_open
        if since_open < 0:
            since_open = 0
        
        # Window size in seconds
        window_size = self.timeframe_minutes * 60
        
        # Which window index?
        window_index = since_open // window_size
        
        # Window start in seconds since midnight
        window_start_seconds = market_open + (window_index * window_size)
        
        # Convert back to UTC timestamp (ms)
        midnight_utc = (ts_sec + ist_offset) - seconds_since_midnight - ist_offset
        start_ts = (midnight_utc + window_start_seconds - ist_offset) * 1000
        
        return start_ts
    
    def on_1min_candle(self, candle) -> Optional[H1Candle]:
        """
        Process a 1-minute candle and returns Aggregated candle if period completed.
        """
        symbol = candle.symbol
        candle_ts = candle.ts
        
        # Initialize if first candle for symbol
        if symbol not in self.current_window:
            self.current_window[symbol] = []
            self.history_candles[symbol] = deque(maxlen=self.sma_period + 10)
            self.window_start_ts[symbol] = self._get_window_start(candle_ts)
            self.bias[symbol] = None
            self.bias_count[symbol] = 0
            self.bias_direction[symbol] = ""
        
        # Check if we've moved to a new window
        current_period_start = self._get_window_start(candle_ts)
        
        if current_period_start > self.window_start_ts[symbol]:
            # Period completed - aggregate and emit
            completed_candle = self._aggregate_candle(symbol)
            
            if completed_candle:
                self.history_candles[symbol].append(completed_candle)
                self._update_bias(symbol, completed_candle)
            
            # Reset for new window
            self.current_window[symbol] = []
            self.window_start_ts[symbol] = current_period_start
        
        # Add to current window
        self.current_window[symbol].append({
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "ts": candle.ts
        })
        
        return None
    
    def _aggregate_candle(self, symbol: str) -> Optional[H1Candle]:
        """Aggregate 1-min candles into timeframed candle"""
        candles = self.current_window.get(symbol, [])
        if not candles:
            return None
        
        return H1Candle(
            symbol=symbol,
            open=candles[0]["open"],
            high=max(c["high"] for c in candles),
            low=min(c["low"] for c in candles),
            close=candles[-1]["close"],
            volume=sum(c["volume"] for c in candles),
            ts=candles[-1]["ts"]
        )
    
    def _calculate_sma(self, symbol: str) -> Optional[float]:
        """Calculate SMA on timeframe closes"""
        candles = list(self.history_candles.get(symbol, []))
        if len(candles) < self.sma_period:
            return None
        
        recent = candles[-self.sma_period:]
        return sum(c.close for c in recent) / self.sma_period
    
    def _update_bias(self, symbol: str, candle: H1Candle):
        """Update BULLISH/BEARISH bias based on SMA relationship"""
        sma = self._calculate_sma(symbol)
        if sma is None:
            return
        
        # Determine direction
        if candle.close > sma:
            direction = "BULLISH"
        elif candle.close < sma:
            direction = "BEARISH"
        else:
            return
        
        # Check if same direction as before
        if direction == self.bias_direction.get(symbol):
            self.bias_count[symbol] = self.bias_count.get(symbol, 0) + 1
        else:
            self.bias_direction[symbol] = direction
            self.bias_count[symbol] = 1
        
        # Confirm bias after N consecutive candles
        if self.bias_count[symbol] >= self.bias_confirm_candles:
            self.bias[symbol] = direction
            print(f"[{self.timeframe_minutes}m] {symbol} BIAS: {direction} (SMA50: {sma:.2f}, Close: {candle.close:.2f})")
    
    def get_bias(self, symbol: str) -> Optional[str]:
        """
        Returns current bias for symbol.
        "BULLISH" - Only take LONG trades
        "BEARISH" - Only take SHORT trades
        None - No clear bias, no trades
        """
        return self.bias.get(symbol)
    
    def get_h1_levels(self, symbol: str) -> Dict[str, float]:
        """
        Returns swing high/low for S/R reference from current timeframe.
        """
        candles = list(self.history_candles.get(symbol, []))
        if len(candles) < 3:
            return {}
        
        # Last 3 H1 candles for swing detection
        recent = candles[-5:] if len(candles) >= 5 else candles
        
        return {
            "h1_high": max(c.high for c in recent),
            "h1_low": min(c.low for c in recent),
            "h1_close": recent[-1].close if recent else None
        }
    
    def allows_trade(self, symbol: str, side: str) -> bool:
        """
        Check if trade direction aligns with H1 bias.
        """
        bias = self.get_bias(symbol)
        
        if bias is None:
            return False  # No clear bias - no trading
        
        if side == "LONG" and bias == "BULLISH":
            return True
        if side == "SHORT" and bias == "BEARISH":
            return True
        
        return False
