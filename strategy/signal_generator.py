# =========================
# FILE: signal_generator.py
# =========================
# Phase 2: Signal Generation Enhancement
# Implements FR-SIG-001 (Pullback to H1 S/R) and FR-SIG-002 (Reversal Patterns)

from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class Candle:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int

class SignalGenerator:
    """
    Generates entry signals based on:
    1. Pullback to key levels (H1 support/resistance)
    2. Candlestick reversal patterns (Hammer, Engulfing)
    """
    
    def __init__(self):
        pass
        
    def check_pullback(self, candle: Candle, h1_levels: Dict[str, float], bias: str) -> bool:
        """
        FR-SIG-001: Check if price pulled back to key H1 level.
        
        BULLISH: Price touches/nears H1 Low or H1 Close of previous candle
        BEARISH: Price touches/nears H1 High or H1 Close of previous candle
        """
        if not h1_levels:
            return False
            
        # Define "near" as within 0.1% or close to it
        threshold_pct = 0.001
        
        if bias == "BULLISH":
            # Check pullback to support (Previous H1 Low)
            support = h1_levels.get("h1_low")
            if not support:
                return False
                
            # Current low touched near support?
            dist_to_support = abs(candle.low - support) / support
            return dist_to_support <= threshold_pct
            
        elif bias == "BEARISH":
            # Check pullback to resistance (Previous H1 High)
            resistance = h1_levels.get("h1_high")
            if not resistance:
                return False
                
            # Current high touched near resistance?
            dist_to_resistance = abs(candle.high - resistance) / resistance
            return dist_to_resistance <= threshold_pct
            
        return False

    def check_reversal_pattern(self, candle: Candle, bias: str) -> bool:
        """
        FR-SIG-002: Detect reversal patterns aligned with bias.
        
        BULLISH: Hammer, Bullish Engulfing (need previous candle for engulfing, keeping simple for now with Hammer)
        BEARISH: Shooting Star, Bearish Engulfing
        """
        body = abs(candle.close - candle.open)
        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low
        total_range = candle.high - candle.low
        
        if total_range == 0:
            return False
            
        if bias == "BULLISH":
            # HAMMER: Long lower wick (> 2x body), small upper wick
            is_hammer = (lower_wick > 2 * body) and (upper_wick < body)
            return is_hammer
            
        elif bias == "BEARISH":
            # SHOOTING STAR: Long upper wick (> 2x body), small lower wick
            is_shooting_star = (upper_wick > 2 * body) and (lower_wick < body)
            return is_shooting_star
            
        return False
        
    def get_signal(self, candle: Candle, h1_levels: Dict[str, float], bias: str) -> Optional[str]:
        """
        Combined signal check:
        1. Context matches (Bias)
        2. Pullback valid (optional strength, but good for confirmation)
        3. Reversal pattern detected (Trigger)
        """
        if not bias:
            return None
            
        # Primary Trigger: Reversal Pattern
        if self.check_reversal_pattern(candle, bias):
            # Confirmation: Did it happen at a key level? 
            # (Strict FR-SIG-001 says "Upon a pullback... system must detect reversal")
            # We can treat pullback check as a filter or a booster.
            # For now, let's require it to be somewhat near the extreme to avoid random noise.
            
            if self.check_pullback(candle, h1_levels, bias):
                return bias # "BULLISH" or "BEARISH"
            
            # If not strict pullback, maybe weak signal? 
            # Let's be strict as per plan.
            
        return None
