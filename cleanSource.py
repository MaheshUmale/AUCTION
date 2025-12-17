from pymongo import MongoClient

# Configuration
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "upstox_strategy_db"
COLLECTION_NAME = "tick_data"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# Aggressive filter to catch 0, "0", 0.0, or nulls across both feed types
delete_filter = {
    "$or": [
        # 1. MarketFF (Equity/FO) Cleanup
        {"fullFeed.marketFF.ltpc.ltp": {"$in": [0, 0.0, "0", None]}},
        {"fullFeed.marketFF.ltpc.ltt": {"$in": ["0", 0, None]}},
        
        # 2. IndexFF (Nifty/Sensex) Cleanup
        {"fullFeed.indexFF.ltpc.ltp": {"$in": [0, 0.0, "0", None]}},
        {"fullFeed.indexFF.ltpc.ltt": {"$in": ["0", 0, None]}}
    ]
}

def purge_source():
    print(f"Connecting to {DB_NAME}.{COLLECTION_NAME}...")
    
    # Pre-check count
    total_to_delete = collection.count_documents(delete_filter)
    
    if total_to_delete == 0:
        print("✅ No junk records (LTP=0 or LTT=0) found in source. Your DB is already clean.")
        return

    print(f"⚠️ Found {total_to_delete} junk records to be deleted.")
    confirm = input("Are you sure you want to permanently DROP these from MongoDB? (yes/no): ")
    
    if confirm.lower() == 'yes':
        result = collection.delete_many(delete_filter)
        print(f"Successfully dropped {result.deleted_count} records from source.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    purge_source()