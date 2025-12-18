from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

fp_col = db.footprints
dom_col = db.dom_snapshots

async def store_footprint(symbol, data):
    await fp_col.insert_one({"symbol": symbol, **data})

async def store_dom(symbol, data):
    await dom_col.insert_one({"symbol": symbol, **data})
