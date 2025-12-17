
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from collections import defaultdict
import time

# Source
SRC_URI = "mongodb://localhost:27017"
SRC_DB = "upstox_strategy_db"
SRC_COL = "tick_data"

# Dest
DST_URI = "mongodb://localhost:27017"
DST_DB = "auction_trading"
DST_COL = "footprints"

# Config
FOOTPRINT_TF_SEC = 60

async def backfill():
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient(SRC_URI)
    src_db = client[SRC_DB]
    src_col = src_db[SRC_COL]
    
    dst_db = client[DST_DB]
    dst_col = dst_db[DST_COL]
    
    # 1. Get Symbols
    print("Fetching symbols...")
    symbols = await src_col.distinct("instrumentKey")
    print(f"Found {len(symbols)} symbols")
    
    for symbol in symbols:
        # Optimization: Only process relevant symbols if needed. 
        # For now, process all found.
        
        print(f"\nProcessing {symbol}...")
        
        # Sort by insertion time implies sort by arrival, which usually correlates with LTT.
        # But correctly we should rely on LTT. 
        # However, we can't sort by nested LTT easily in Mongo if index doesn't exist.
        # We'll pull by insertion time and handle timestamp logic in code.
        cursor = src_col.find({"instrumentKey": symbol}).sort("_insertion_time", 1)
        
        current_bucket_ts = 0
        levels = defaultdict(lambda: {"bid": 0, "ask": 0})
        count = 0
        PROCESSED_TICKS = 0
        
        async for doc in cursor:
            PROCESSED_TICKS += 1
            full_feed = doc.get("fullFeed", {})
            
            # 1. Identify Feed Type (Market vs Index)
            ff_data = full_feed.get("marketFF") or full_feed.get("indexFF")
            if not ff_data:
                continue
                
            # 2. Extract LTPC
            ltpc = ff_data.get("ltpc", {})
            if not ltpc:
                continue
                
            # 3. Extract Timestamp (LTT)
            # "ltt": "1765856700266" (String Epoch MS)
            ltt_str = ltpc.get("ltt")
            if not ltt_str:
                continue
                
            try:
                ltt_ms = int(ltt_str)
                ts_sec = ltt_ms / 1000.0
            except ValueError:
                continue
                
            # 4. Extract Price and Qty
            ltp = float(ltpc.get("ltp", 0))
            # indexFF won't have ltq usually, default to 0
            ltq_raw = ltpc.get("ltq", 0)
            ltq = int(ltq_raw) if ltq_raw else 0
            
            # Skip noise ticks with 0 qty (unless we want to track price action only, but footprint needs vol)
            if ltq <= 0:
                continue

            # 5. Bucket Logic
            bucket_ts = int(ts_sec // FOOTPRINT_TF_SEC * FOOTPRINT_TF_SEC)
            
            # If moved to new bucket
            if bucket_ts > current_bucket_ts:
                # Save previous bucket
                if current_bucket_ts > 0 and levels:
                    save_doc = {
                        "type": "footprint",
                        "symbol": symbol,
                        "ts": current_bucket_ts,
                        "levels": {str(k): v for k, v in levels.items()},
                        "created_at": datetime.utcnow() # Meta field
                    }
                    
                    # Upsert
                    await dst_col.update_one(
                        {"symbol": symbol, "ts": current_bucket_ts, "type": "footprint"},
                        {"$set": save_doc},
                        upsert=True
                    )
                    count += 1
                    if count % 50 == 0:
                        print(f"  Saved {count} bars (Ticks: {PROCESSED_TICKS})...", end="\r")
                
                # Reset
                current_bucket_ts = bucket_ts
                levels = defaultdict(lambda: {"bid": 0, "ask": 0})
            
            # 6. Classify Volume (Bid vs Ask)
            # Use marketLevel bidAskQuote if available
            market_level = ff_data.get("marketLevel", {})
            bid_ask_quote = market_level.get("bidAskQuote", [])
            
            is_buy = True # Default
            
            if bid_ask_quote:
                # Naive match against best bid/ask
                # Note: bidAskQuote array items have bidP, askP
                # Item 0 is usually best
                best = bid_ask_quote[0]
                best_bid = float(best.get("bidP", 0))
                best_ask = float(best.get("askP", 0))
                
                if best_bid > 0 and ltp <= best_bid:
                    is_buy = False # Hit the bid (Sell)
                elif best_ask > 0 and ltp >= best_ask:
                    is_buy = True # Lifted the ask (Buy)
                else:
                    # Mid-spread? Split, or default to Buy?
                    # Let's check previous tick? Too complex for stateless loop.
                    # Defaulting to Buy or keeping 50/50?
                    # Let's split for neutrality if unknown
                    levels[ltp]["bid"] += ltq // 2
                    levels[ltp]["ask"] += ltq // 2
                    is_buy = None # Handled
            
            if is_buy is True:
                levels[ltp]["ask"] += ltq
            elif is_buy is False:
                levels[ltp]["bid"] += ltq
                
        # Save absolute last bucket
        if current_bucket_ts > 0 and levels:
            save_doc = {
                "type": "footprint",
                "symbol": symbol,
                "ts": current_bucket_ts,
                "levels": {str(k): v for k, v in levels.items()},
                "created_at": datetime.utcnow()
            }
            await dst_col.update_one(
                {"symbol": symbol, "ts": current_bucket_ts, "type": "footprint"},
                {"$set": save_doc},
                upsert=True
            )
            count += 1
            
        print(f"  Finished {symbol}: {count} bars created.")

if __name__ == "__main__":
    asyncio.run(backfill())
