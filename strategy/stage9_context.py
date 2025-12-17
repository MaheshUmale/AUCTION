from collections import deque
from typing import Dict, Deque, List, Optional
from strategy.auction_theory import VolumeProfile
import numpy as np
import config
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
        value_area_pct: float = 0.50
    ):
        self.lookback = lookback
        self.tick_size = tick_size
        self.value_area_pct = value_area_pct
        self.candles: Dict[str, Deque[dict]] = {}

    def _calculate_vwap(self, symbol: str, slice_idx: int = 0) -> Optional[float]:
        """
        Calculates VWAP from the rolling candle window.
        slice_idx: Start index for calculation (0 = full window, -5 = last 5 only?). 
                   Actually meaningful is 'up to index N'.
                   Let's compute for the whole list slice.
        """
        candles = list(self.candles.get(symbol, []))
        if not candles:
            return None
            
        # If slice needed (e.g. "VWAP of last 10 candles" vs "VWAP of previous 10")
        # Let's simple calculate VWAP of the list passed.
        # But we need "Point-in-time" VWAP to determine Slope.
        # Better: Calculate VWAP at current moment, and "Last Known VWAP" (e.g. 5 mins ago).
        
        # We can just iterate the slice provided
        subset = candles[slice_idx:] if slice_idx >= 0 else candles[:slice_idx]
        if not subset:
            return None

        cum_pv = 0.0
        cum_vol = 0.0
        
        for c in subset:
            avg_price = (c["high"] + c["low"] + c.get("close", (c["high"]+c["low"])/2)) / 3
            cum_pv += avg_price * c["volume"]
            cum_vol += c["volume"]
            
        return cum_pv / cum_vol if cum_vol > 0 else None

    def _check_igniting_candle(self, symbol: str, current_vol: float, current_ts: int = 0) -> bool:
        """
        Checks if current Flow Rate (Vol/Sec) is > 4 std dev of last 50 bars.
        Includes backward compatibility for Time-based bars.
        """
        candles = list(self.candles.get(symbol, []))
        if len(candles) < 20: # Need some history
            return False
            
        # Get last 50
        subset = candles[-51:-1] 
        if not subset:
            return False
            
        # Calculate Flow Rates
        flow_rates = []
        prev_ts = subset[0]['ts']
        
        for i in range(1, len(subset)):
            c = subset[i]
            duration = (c['ts'] - prev_ts) / 1000 # seconds
            if duration <= 0: duration = 1 # Safety
            rate = c['volume'] / duration
            flow_rates.append(rate)
            prev_ts = c['ts']
            
        if not flow_rates:
             return False
             
        mean_rate = np.mean(flow_rates)
        std_rate = np.std(flow_rates)
        
        # Current Rate
        last_history_ts = candles[-1]['ts']
        # If current_ts not provided (live check before close?), we might assume it's "now" vs last close?
        # Typically this is called with a completed 'candle' object.
        # But 'candles' deque has the history without current?
        # The logic in 'classify' calls this.
        
        # Logic fix: pass 'candle' object with ts to this func?
        # Caller passes 'current_vol'. We need 'duration' of current bar?
        # If we are checking "is this candle igniting", we need its duration.
        # We passed 'current_vol' but not duration. 
        # Refactor: We need duration of the candle being checked.
        # Approximation: if we don't have start_ts of 'candle', we can't get duration accurately 
        # unless we know the previous candle ts.
        
        if current_ts <= 0: return False
        
        prev_close_ts = candles[-1]['ts']
        cur_duration = (current_ts - prev_close_ts) / 1000
        if cur_duration <= 0: cur_duration = 1
        
        current_rate = current_vol / cur_duration
        
        # Threshold: Mean + 4 Std Dev
        if current_rate > (mean_rate +  config.STD_DEV * std_rate):
            return True
        elif current_vol > (np.mean([x['volume'] for x in subset]) + config.STD_DEV * np.std([x['volume'] for x in subset])):
             # Fallback: Also trigger if RAW Volume is huge (e.g. extremely high volume in slow time)
             return True
             
        return False

    def classify_high_volume_bar(self, candle) -> str:
        """
        Classifies high-volume bars into types:
        
        Returns:
            'IGNITING' - Continuation signal (strong body, close near extreme)
            'EXHAUSTION' - Reversal warning (long wick, rejection)
            'NORMAL' - Not a high-volume bar
        
        IGNITING (continuation):
        - Volume > 4 std dev
        - Body > 50% of range
        - Close near candle extreme (small wick on closing side)
        
        EXHAUSTION (reversal warning):
        - Volume > 4 std dev  
        - Body < 30% of range (long wicks = rejection)
        """
        if not self._check_igniting_candle(candle.symbol, candle.volume, candle.ts):
            return 'NORMAL'
        
        body = abs(candle.close - candle.open)
        range_size = candle.high - candle.low
        
        if range_size == 0:
            return 'NORMAL'
        
        body_ratio = body / range_size
        
        # IGNITING: Strong body with close near extreme
        if body_ratio > 0.5:
            if candle.close > candle.open:  # Green candle
                # Close should be near high (small upper wick)
                close_to_high_pct = (candle.high - candle.close) / range_size
                if close_to_high_pct < 0.2:
                    return 'IGNITING'
            else:  # Red candle
                # Close should be near low (small lower wick)
                close_to_low_pct = (candle.close - candle.low) / range_size
                if close_to_low_pct < 0.2:
                    return 'IGNITING'
        
        # EXHAUSTION: Long wicks indicate rejection
        if body_ratio < 0.3:
            return 'EXHAUSTION'
        
        return 'NORMAL'

    def _get_high_vol_reaction_zone(self, symbol: str) -> Optional[Dict]:
        """
        Finds highest volume candle in last 100 bars.
        Returns Price Zone (Start, End) based on wicks.
        Red Candle -> Upper Wick Zone (Resistance)
        Green Candle -> Lower Wick Zone (Support)
        """
        candles = list(self.candles.get(symbol, []))
        if len(candles) < 20: 
            return None
            
        # Last 100
        subset = candles[-100:]
        
        # Find Max Vol Candle
        max_vol_candle = max(subset, key=lambda c: c['volume'])
        
        # Define Zone
        # If Green (Close > Open) -> Lower Wick is support? 
        # User said: "extend line/zone ( upper wick if red/ lower wick if green)"
        # We don't save Open in 'candles' deque currently! We only save low, high, close, volume.
        # Oh, Stage9 _update_candles saves: low, high, close, volume. NO OPEN.
        # We need OPEN to determine color.
        # I will patch _update_candles to save Open.
        
        # Access open if available, else approximate? 
        # I'll update _update_candles to save 'open' first.
        
        c = max_vol_candle
        if 'open' not in c:
             return None # Can't determine color
             
        zone = {}
        if c['close'] < c['open']: # Red
            # Upper Wick: Open to High
            zone = {'type': 'RESISTANCE', 'top': c['high'], 'bottom': c['open']}
        else: # Green
            # Lower Wick: Open to Low
            zone = {'type': 'SUPPORT', 'top': c['open'], 'bottom': c['low']}
            
        return zone

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
        self._update_candles(candle)
        candles_list = list(self.candles.get(candle.symbol, []))

        if len(candles_list) < self.lookback:
            return False
            
        # --- 0. CHECK IGNITING CANDLE (High Priority Trend) ---
        if self._check_igniting_candle(candle.symbol, candle.volume, candle.ts):
            # If volume is huge, we follow the move immediately if direction matches
            if side == "LONG" and candle.close > candle.open: # Green Igniting
                 return True
            if side == "SHORT" and candle.close < candle.open: # Red Igniting
                 return True

        vp = self._get_volume_profile(candle.symbol)
        vwap_now = self._calculate_vwap(candle.symbol)
        
        if not all([vp, vp.poc, vp.vah, vp.val, vwap_now]):
            return False
            
        dist_to_vwap_pct = abs(candle.close - vwap_now) / vwap_now
        avg_vol = sum(c['volume'] for c in candles_list) / len(candles_list)
        vol_ratio = candle.volume / avg_vol if avg_vol > 0 else 0
        
        # --- 1. CHOP FILTER ---
        if dist_to_vwap_pct < 0.0005 and vol_ratio < 1.5:
             return False

        # --- 2. REACTION ZONE FILTER ---
        # If we are hitting a reaction zone, be careful
        rx_zone = self._get_high_vol_reaction_zone(candle.symbol)
        if rx_zone:
            if side == "LONG" and rx_zone['type'] == 'RESISTANCE':
                # Don't buy into resistance zone
                if candle.close >= rx_zone['bottom'] and candle.close <= rx_zone['top']:
                    return False 
            if side == "SHORT" and rx_zone['type'] == 'SUPPORT':
                # Don't sell into support zone
                if candle.close >= rx_zone['bottom'] and candle.close <= rx_zone['top']:
                    return False

        # --- 3. Regime-Based Entry (Incorporating VWAP Filter) ---
        if vp.is_balanced:
            # Mean Reversion Mode: Buy Low, Sell High (VWAP ignored or used as target)
            if side == "LONG" and candle.close <= vp.val:
                 return True
            if side == "SHORT" and candle.close >= vp.vah:
                 return True
        else:
            # Trending Mode: Apply VWAP Filter Here
            dominant_side = vp.dominant_side
            if vol_ratio < 0.8: 
                return False
            
            # VWAP FILTER IMPL:
            if side == "LONG" and candle.close < vwap_now:
                 return False # Don't buy downtrend
            if side == "SHORT" and candle.close > vwap_now:
                 return False # Don't sell uptrend

            if side == "LONG" and dominant_side == "BUYER":
                if candle.close >= vp.vah: 
                    return True
                if candle.close <= vp.vah and candle.close >= vp.val: 
                    return True
                    
            if side == "SHORT" and dominant_side == "SELLER":
                if candle.close <= vp.val: 
                    return True
                if candle.close >= vp.val and candle.close <= vp.vah: 
                    return True

        return False

    def _update_candles(self, candle):
        """Maintains a rolling window of recent candles."""
        if candle.symbol not in self.candles:
            self.candles[candle.symbol] = deque(maxlen=self.lookback)
        self.candles[candle.symbol].append({
            "open": candle.open, # Added Open
            "low": candle.low,
            "high": candle.high,
            "close": candle.close,
            "high": candle.high,
            "close": candle.close,
            "volume": candle.volume,
            "ts": candle.ts # Added Timestamp
        })
