
import sys
import os
import pymongo
import time
import random

# Setup paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "AUCTION"))

import config
from AUCTION.stage8_engine import LiveAuctionEngine, Candle
from AUCTION.footprint_engine import FootprintBuilder

def run_test():
    print(">>> STARTING STRATEGY TEST (MAXHEALTH RECENT DATA) <<<")
    
    # 1. Init DB
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client["upstox_strategy_db"]
    tick_col = db["tick_data"]
    
    # Target Symbol from User Request
    symbol = "NSE_EQ|INE027H01010"
    print(f"Target: {symbol}")
    
    # 2. Fetch Recent Data (Last 200,000 ticks)
    print("Fetching last 200,000 ticks to simulate TODAY's action...")
    # Sort DESC (latest first) by Insertion Time (more reliable than ltt if missing)
    cursor = tick_col.find({"instrumentKey": symbol}).sort("_insertion_time", -1).limit(200000)
    
    # Convert to list and REVERSE to get chronological order (Oldest -> Newest)
    ticks = list(cursor)
    ticks.reverse()
    
    print(f"Loaded {len(ticks)} ticks. Replaying...")
    if ticks:
        # Safe get access
        t1 = ticks[0].get('ltt') or ticks[0].get('_insertion_time')
        t2 = ticks[-1].get('ltt') or ticks[-1].get('_insertion_time')
        print(f"First Tick TS: {t1}")
        print(f"Last Tick TS: {t2}")
        
    print(f"Config TF_SEC: {config.FOOTPRINT_TF_SEC}")
    
    # 3. Init Engine
    engine = LiveAuctionEngine(simulation_mode=True, persistence_db_name="auction_test_verification")
    fb = FootprintBuilder(tf_sec=config.FOOTPRINT_TF_SEC)
    
    total_trades = 0
    tick_count = 0
    
    # 4. Process Ticks
    for doc in ticks:
        tick_count += 1
        if tick_count % 5000 == 0:
             print(f"Processed {tick_count} ticks...", end='\r')
        
        # Parse Tick
        ltp = float(doc.get("ltp", 0))
        # Use 'v' (Day Volume) or 'ltq' (Last Qty). 
        # Upstox 'v' is cumulative volume. 'ltq' is tick volume.
        # If 'ltq' missing, we can diff 'v'? No, 'ltq' is safer if available.
        ltq = float(doc.get("ltq", 0)) 
        if ltq == 0 and doc.get("v"):
             # Fallback if ltq is 0 but V changes? Hard to track prev V here.
             # Just assume 0.
             pass
             
        # Timestamp
        ltt = doc.get("ltt")
        if not ltt: ltt = doc.get("_insertion_time").timestamp() * 1000
        ts = float(ltt)
        
        # Side Simulation (Naive)
        side = "BUY" 
        
        # Update Footprint
        fb.on_tick(ltp, ltq, side)
        
        # Check Rotation
        snap, rotated = fb.check_rotation(ts / 1000)
        
        if rotated and snap:
            print(f"Candle Formed at {snap['ts']} Vol: {snap['volume']}")
            # Create Candle
            c = Candle(
                symbol=symbol,
                open=snap['open'],
                high=snap['high'],
                low=snap['low'],
                close=snap['close'],
                volume=snap['volume'],
                ts=snap['ts']
            )
            
            # Feed to Engine
            # This triggers all logic: Volume, Context, H1, Signal
            engine.on_candle_close(c)
            
            # Check for generic trade entry
            if engine.trade_engine.has_open_trade(symbol):
                print(f"\n  *** TRADE ENTRY ***: {symbol} at {c.ts} Price: {c.close}")
                total_trades += 1
                engine.trade_engine.close_trade(symbol, c.close, "TEST_CLOSE")

    print(f"\n>>> TEST COMPLETE. Total Trades Triggered: {total_trades} <<<")

if __name__ == "__main__":
    run_test()
