# =========================
# FILE: orderbook_analyzer.py
# =========================
# Phase 3: Level 2 Order Book Integration
# Analyzes 5-level bid/ask depth for entry confirmation

from collections import deque
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class OrderBookSnapshot:
    """5-level order book snapshot"""
    symbol: str
    ts: int
    bids: List[Tuple[float, int]]  # [(price, qty), ...]
    asks: List[Tuple[float, int]]  # [(price, qty), ...]
    tbq: int  # Total buy quantity
    tsq: int  # Total sell quantity


class OrderBookAnalyzer:
    """
    Analyzes Level 2 order book data for:
    - TBQ/TSQ imbalance (1.5x rule)
    - Absorption detection (large bid holding price)
    - Wall detection (large ask blocking price)
    - Best bid/ask tracking for entry/SL
    """
    
    def __init__(self, imbalance_ratio: float = 1.5):
        self.imbalance_ratio = imbalance_ratio
        
        # symbol -> latest order book snapshot
        self.current_book: Dict[str, OrderBookSnapshot] = {}
        
        # symbol -> deque of recent snapshots for absorption detection
        self.book_history: Dict[str, deque] = {}
    
    def update(self, symbol: str, market_ff: dict, ts: int):
        """
        Update order book from WSS marketFF data.
        
        Expected format:
        {
            "marketLevel": {
                "bidAskQuote": [
                    {"bidQ": "75", "bidP": 213.45, "askQ": "525", "askP": 213.9},
                    ...
                ]
            },
            "tbq": 46050,
            "tsq": 41850
        }
        """
        market_level = market_ff.get("marketLevel", {})
        bid_ask = market_level.get("bidAskQuote", [])
        
        if not bid_ask:
            return
        
        # Parse bids and asks
        bids = []
        asks = []
        for level in bid_ask:
            bid_price = level.get("bidP", 0)
            bid_qty = int(level.get("bidQ", 0))
            ask_price = level.get("askP", 0)
            ask_qty = int(level.get("askQ", 0))
            
            if bid_price and bid_qty:
                bids.append((bid_price, bid_qty))
            if ask_price and ask_qty:
                asks.append((ask_price, ask_qty))
        
        # Get TBQ/TSQ
        tbq = int(market_ff.get("tbq", 0))
        tsq = int(market_ff.get("tsq", 0))
        
        snapshot = OrderBookSnapshot(
            symbol=symbol,
            ts=ts,
            bids=bids,
            asks=asks,
            tbq=tbq,
            tsq=tsq
        )
        
        self.current_book[symbol] = snapshot
        
        # Track history for absorption detection
        if symbol not in self.book_history:
            self.book_history[symbol] = deque(maxlen=20)
        self.book_history[symbol].append(snapshot)
    
    def check_entry_imbalance(self, symbol: str, side: str) -> bool:
        """
        FR-EXEC-001: Check if TBQ/TSQ imbalance confirms entry.
        
        Bullish: TBQ > 1.5 * TSQ
        Bearish: TSQ > 1.5 * TBQ
        """
        book = self.current_book.get(symbol)
        if not book:
            return False
        
        if book.tbq == 0 or book.tsq == 0:
            return False
        
        if side == "LONG":
            return book.tbq > (book.tsq * self.imbalance_ratio)
        else:  # SHORT
            return book.tsq > (book.tbq * self.imbalance_ratio)
    
    def get_best_bid(self, symbol: str) -> Optional[Tuple[float, int]]:
        """Get best bid price and quantity"""
        book = self.current_book.get(symbol)
        if not book or not book.bids:
            return None
        return book.bids[0]
    
    def get_best_ask(self, symbol: str) -> Optional[Tuple[float, int]]:
        """Get best ask price and quantity"""
        book = self.current_book.get(symbol)
        if not book or not book.asks:
            return None
        return book.asks[0]
    
    def check_absorption(self, symbol: str, side: str) -> bool:
        """
        FR-EXEC-002: Check if large bid/ask is absorbing pressure.
        
        For LONG: Large bid quantity holding while asks getting hit
        For SHORT: Large ask quantity holding while bids getting lifted
        """
        history = list(self.book_history.get(symbol, []))
        if len(history) < 5:
            return False
        
        recent = history[-5:]
        
        if side == "LONG":
            # Check if best bid qty remained large while price held
            bid_qtys = [h.bids[0][1] if h.bids else 0 for h in recent]
            bid_prices = [h.bids[0][0] if h.bids else 0 for h in recent]
            
            # Bid held steady (price didn't drop) with strong qty
            avg_qty = sum(bid_qtys) / len(bid_qtys) if bid_qtys else 0
            price_held = all(p >= bid_prices[0] * 0.999 for p in bid_prices)
            
            return avg_qty > 500 and price_held
        else:
            # Check if best ask qty remained large while price held
            ask_qtys = [h.asks[0][1] if h.asks else 0 for h in recent]
            ask_prices = [h.asks[0][0] if h.asks else 0 for h in recent]
            
            avg_qty = sum(ask_qtys) / len(ask_qtys) if ask_qtys else 0
            price_held = all(p <= ask_prices[0] * 1.001 for p in ask_prices)
            
            return avg_qty > 500 and price_held
    
    def detect_wall(self, symbol: str, direction: str) -> Optional[float]:
        """
        FR-EXEC-005: Detect sell wall (for longs) or buy wall (for shorts).
        Returns wall price if detected, None otherwise.
        
        Wall = Large quantity at single price level (> 3x avg)
        """
        book = self.current_book.get(symbol)
        if not book:
            return None
        
        if direction == "UP":  # Looking for sell wall (large ask)
            if not book.asks:
                return None
            
            avg_ask_qty = sum(a[1] for a in book.asks) / len(book.asks)
            for price, qty in book.asks:
                if qty > avg_ask_qty * 3:
                    return price
        else:  # Looking for buy wall (large bid)
            if not book.bids:
                return None
            
            avg_bid_qty = sum(b[1] for b in book.bids) / len(book.bids)
            for price, qty in book.bids:
                if qty > avg_bid_qty * 3:
                    return price
        
        return None
    
    def get_entry_price(self, symbol: str, side: str) -> Optional[float]:
        """
        FR-EXEC-003: Get entry price at best bid (LONG) or best ask (SHORT).
        """
        if side == "LONG":
            bid = self.get_best_bid(symbol)
            return bid[0] if bid else None
        else:
            ask = self.get_best_ask(symbol)
            return ask[0] if ask else None
    
    def get_dynamic_stop(self, symbol: str, side: str, candle_low: float, candle_high: float, tick_size: float = 0.05) -> float:
        """
        FR-EXEC-004: Dynamic stop loss.
        
        LONG: MAX(1 tick below best bid, below candle low)
        SHORT: MIN(1 tick above best ask, above candle high)
        """
        if side == "LONG":
            bid = self.get_best_bid(symbol)
            bid_stop = (bid[0] - tick_size) if bid else candle_low
            return min(bid_stop, candle_low - tick_size)
        else:
            ask = self.get_best_ask(symbol)
            ask_stop = (ask[0] + tick_size) if ask else candle_high
            return max(ask_stop, candle_high + tick_size)
