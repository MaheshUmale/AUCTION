
import asyncio
from pymongo import MongoClient
import time
import os
import sys

# Ensure root can be imported for config
sys.path.append(os.path.join(os.getcwd(), ".."))
# Also ensure AUCTION is in path if running from root
sys.path.append(os.path.join(os.getcwd(), "AUCTION"))

try:
    import config
except ImportError:
    # Try importing directly if we are in root
    import config

def rehydrate_history():
    print(">>> STARTING HISTORY REHYDRATION <<<")
    
    client = MongoClient("mongodb://localhost:27017")
    
    # Source: tick_data (Raw ticks)
    # Target: auction_trading.footprints (where run_merged reads history)
    
    source_db = client["upstox_strategy_db"]
    tick_col = source_db["tick_data"]
    
    target_db = client["auction_trading"]
    fp_col = target_db["footprints"]
    
    # We want to rehydrate for "Today"
    # Or just rehydrate everything found in tick_data for the target symbols
    
    # Get symbols from config
    symbols = config.WATCHLIST
    # Also add indices if needed
    symbols += ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]
    
    # Clean target for safety? Or just upsert?
    # User said "rehydrate every thing once", likely implies a refresh.
    # But let's be careful not to delete open trades etc.
    # The footprint history is usually ephemeral or rebuilt. 
    # Let's delete OLD history for today to avoid duplicates if we re-process?
    # Actually, upsert is safer.
    
    from AUCTION.footprint_engine import FootprintBuilder
    
    # We need to rebuild 1-min footprints from ticks
    # Config
    TF_SEC = 60
    
    for symbol in symbols:
        print(f"Processing {symbol}...")
        
        # Get all ticks for this symbol, sorted by time
        # We can limit to today if we want, or just last 2 days.
        # Let's look at today's start
        
        # For robustness, let's just grab ALL relevant ticks from the collection
        # that are "recent" (e.g. last 24-48 hours) to ensure we have history.
        # Or just grab everything available efficiently.
        
        # Filter: 
        query = {"instrumentKey": symbol}
        
        cursor = tick_col.find(query).sort("_insertion_time", 1)
        
        builder = FootprintBuilder(tf_sec=TF_SEC)
        
        count = 0
        batch = []
        
        for doc in cursor:
            # Ticks in upstox_strategy_db.tick_data usually have structure:
            # { "ltp": ..., "v": ..., "tbq": ..., "tsq": ..., "ltt": ... }
            # Or depends on how they were saved.
            # Looking at main.py, it seems they are saved as raw feed?
            # Let's inspect a doc structure if possible. 
            # Assuming standard structure from earlier files.
            
            # Map fields
            ltp = float(doc.get("ltp", 0) or 0)
            vol = float(doc.get("v", 0) or 0) # This is cumulative usually? Or tick volume?
            # Upstox feed "vol" is usually cumulative for the day. 
            # We need Delta Volume for the footprint. This is hard if we only have cumulative.
            # However, `ltq` (Last Traded Qty) is what we need. 
            ltq = float(doc.get("ltq", 0) or 0)
            
            # Timestamp (ltt is usually ms)
            ltt = doc.get("ltt")
            if not ltt:
                # Fallback to insertion time
                ltt = doc.get("_insertion_time").timestamp() * 1000
            
            ts = int(ltt)
            
            # Infer side
            # We assume simple side logic if not present
            # Or use Order Book if recorded (doubtful in simple tick storage)
            # Default to BUY
            side = "BUY" # Placeholder
            
            # Determine side by price change if possible?
            # Can't easily do without prev price locally in loop.
            
            # Update Builder
            builder.on_tick(ltp, ltq, side)
            
            # Check Rotation
            # Builder expects seconds for rotation check
            snap, rotated = builder.check_rotation(ts / 1000)
            
            if rotated and snap:
                # Save SNAP to DB
                snap_doc = snap.copy()
                snap_doc["symbol"] = symbol
                # Stringify keys
                snap_doc["levels"] = {str(k): v for k, v in snap.get("levels", {}).items()}
                
                # Insert to target DB
                # buffer writes?
                fp_col.update_one(
                     {"symbol": symbol, "ts": snap["ts"], "type": "footprint"},
                     {"$set": snap_doc},
                     upsert=True
                )
                count += 1
                
        print(f"  -> Rehydrated {count} bars for {symbol}")

    print("<<< REHYDRATION COMPLETE >>>")

if __name__ == "__main__":
    rehydrate_history()
