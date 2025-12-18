
from pymongo import MongoClient
import pprint

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "market_fp"
COL_FOOTPRINT = "footprints"

def check_data():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COL_FOOTPRINT]
    
    symbol = "NSE_EQ|INE758T01015"
    print(f"Checking data for {symbol}...")
    
    # Get last 5 docs
    cursor = col.find({"symbol": symbol}).sort("ts", -1).limit(5)
    
    count = 0
    for doc in cursor:
        count += 1
        print("\n--------------------------------")
        print("Keys:", list(doc.keys()))
        if 'levels' in doc:
            print("Levels count:", len(doc['levels']))
            if len(doc['levels']) > 0:
                first_key = next(iter(doc['levels']))
                print(f"Sample Level [{first_key}]:", doc['levels'][first_key])
                print(f"Sample Level Type:", type(doc['levels'][first_key]))
        else:
            print("NO LEVELS FOUND")
        
        if 'type' in doc:
            print("Type:", doc['type'])
            
    print(f"\nTotal docs found: {count}")

if __name__ == "__main__":
    check_data()
