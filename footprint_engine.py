import time
from collections import defaultdict
from typing import Dict, Optional


import os
import sys
# Ensure root module can be imported
sys.path.append(os.path.join( "D:\\newFootprintChart\\"))
import config

class FootprintBuilder:
    def __init__(self, tf_sec=60, vol_threshold=None, tick_threshold=None):
        self.tf_sec = tf_sec
        
        # Hybrid Thresholds (Argument -> Config -> Default)
        if vol_threshold is not None:
             self.vol_threshold = vol_threshold
        else:
             self.vol_threshold = getattr(config, 'FOOTPRINT_VOL_THRESHOLD', 5000)
             
        if tick_threshold is not None:
             self.tick_threshold = tick_threshold
        else:
             self.tick_threshold = getattr(config, 'FOOTPRINT_TICK_THRESHOLD', 300)
        
        self.start_ts = int(time.time()) # Start immediately
        
        # levels: price -> {bid_vol, ask_vol, absorption_flag}
        self.levels = defaultdict(lambda: {"bid": 0, "ask": 0, "abs": 0})
        self.last_ltp = 0
        
        # Candle Stats
        self.open = 0.0
        self.high = 0.0
        self.low = float('inf')
        self.close = 0.0
        self.volume = 0.0
        self.tick_count = 0
        self.is_first_tick = True

    def reset(self, ts=None):
        if ts:
            self.start_ts = int(ts) # Use exact TS provided
        else:
            self.start_ts = int(time.time())
            
        self.levels = defaultdict(lambda: {"bid": 0, "ask": 0, "abs": 0})
        
        self.open = 0.0
        self.high = 0.0
        self.low = float('inf')
        self.close = 0.0
        self.volume = 0.0
        self.tick_count = 0
        self.is_first_tick = True

    def check_rotation(self, current_ts_sec):
        # 1. Check Time Duration
        time_elapsed = current_ts_sec - self.start_ts
        time_rotated = time_elapsed >= self.tf_sec
        
        # 2. Check Volume
        vol_rotated = self.volume >= self.vol_threshold
        
        # 3. Check Ticks
        tick_rotated = self.tick_count >= self.tick_threshold
        
        if time_rotated or vol_rotated or tick_rotated:
            snapshot = self.snapshot()
            
            # Reset for NEXT bar starts NOW (or at current_ts_sec)
            # This creates a "Hybrid" series where bars are sequential but variable duration
            self.reset(ts=current_ts_sec)
            
            # Debug log if needed (optional)
            # reason = "TIME" if time_rotated else ("VOL" if vol_rotated else "TICK")
            # print(f"Rotate [{reason}] Vol:{snapshot['volume']} Ticks:{self.tick_count} Dur:{time_elapsed}s")
            
            return snapshot, True 
            
        return None, False

    def on_tick(self, ltp: float, ltq: int, side: str, absorption: bool = False):
        if ltq <= 0: return 
        
        # OHLC Logic
        if self.is_first_tick:
            self.open = ltp
            self.high = ltp
            self.low = ltp
            self.is_first_tick = False
        
        self.high = max(self.high, ltp)
        self.low = min(self.low, ltp)
        self.close = ltp
        self.volume += ltq
        self.tick_count += 1

        lvl = self.levels[ltp]
        if side == "BUY":
            lvl["ask"] += ltq
        elif side == "SELL":
            lvl["bid"] += ltq
        
        if absorption:
            lvl["abs"] = 1 

    def snapshot(self, atp=0):
        delta = sum(v["ask"] - v["bid"] for v in self.levels.values())
        return {
            "type": "footprint",
            "ts": self.start_ts * 1000, # Convert back to ms for compatibility
            "levels": dict(self.levels),
            "delta": delta,
            "vwap": atp,
            "open": self.open,
            "high": self.high,
            "low": self.low if self.low != float('inf') else 0, # Safety
            "close": self.close,
            "volume": self.volume,
            "ticks": self.tick_count
        }
