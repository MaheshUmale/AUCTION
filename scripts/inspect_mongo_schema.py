
import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["upstox_strategy_db"]
col = db["tick_data"]

print("--- EQUITY SAMPLE ---")
# Find one that is NOT index
pipeline_eq = [{"$match": {"instrumentKey": {"$not": {"$regex": "INDEX|Nifty"}}}}, {"$limit": 1}]
eq_doc = list(col.aggregate(pipeline_eq))
if eq_doc:
    ff = eq_doc[0].get('fullFeed', {})
    print("Equity fullFeed Keys:", ff.keys())
    # Recursively check marketLevel
    if 'marketLevel' in ff:
        print("  marketLevel Keys:", ff['marketLevel'].keys())
        # Print sample depth
        print("  Depth Sample:", ff['marketLevel'].get('bidAskQuote', [])[:1])
    else:
        print("Flattened keys in fullFeed:", ff)

print("\n--- INDEX SAMPLE ---")
# Find one that IS index
pipeline_idx = [{"$match": {"instrumentKey": {"$regex": "INDEX|Nifty"}}}, {"$limit": 1}]
idx_doc = list(col.aggregate(pipeline_idx))
if idx_doc:
    print(idx_doc[0])
    for k,v in idx_doc[0].items():
        print(f"  {k}: {type(v)}")
