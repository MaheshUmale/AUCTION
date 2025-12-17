
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "market_fp"
COL_FOOTPRINT = "footprints"

def check_counts():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COL_FOOTPRINT]
    
    symbol = "NSE_EQ|INE758T01015"
    print(f"Checking data for {symbol}...")
    
    total = col.count_documents({"symbol": symbol})
    market = col.count_documents({"symbol": symbol, "type": "market"})
    footprint = col.count_documents({"symbol": symbol, "type": "footprint"})
    
    print(f"Total docs: {total}")
    print(f"Type 'market': {market}")
    print(f"Type 'footprint': {footprint}")
    
    if footprint > 0:
        # Check the latest footprint
        last_fp = col.find_one({"symbol": symbol, "type": "footprint"}, sort=[("ts", -1)])
        print("Latest Footprint keys:", list(last_fp.keys()))
        if 'levels' in last_fp:
            print("Latest Footprint Levels Count:", len(last_fp['levels']))

if __name__ == "__main__":
    check_counts()
