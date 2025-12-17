import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from questdb.ingress import Sender

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
QDB_HOST = '127.0.0.1'
QDB_PORT = 9009 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    m_client = MongoClient(MONGO_URI)
    db = m_client["upstox_strategy_db"]
    col = db["tick_data15Dec"]
    
    # Check if there's anything left to migrate
    cursor = col.find({})
    
    try:
        # Using explicit keywords to avoid the "expected str, got int" error
        with Sender(protocol='tcp', host=QDB_HOST, port=QDB_PORT) as sender:
            count = 0
            for doc in cursor:
                try:
                    f_feed = doc.get('fullFeed', {})
                    mode = 'marketFF' if 'marketFF' in f_feed else 'indexFF'
                    data = f_feed.get(mode, {})
                    ltpc = data.get('ltpc', {})
                    
                    ltt_str = ltpc.get('ltt')
                    if not ltt_str or ltt_str == "0":
                        continue

                    # --- TIMESTAMP FIX ---
                    # Convert ms string to seconds (float) for datetime
                    ts_seconds = int(ltt_str) / 1000.0
                    # Create a datetime object (this is what your library version wants)
                    dt_object = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)

                    symbols = {
                        "instrument_key": str(doc.get('instrumentKey')),
                        "feed_type": mode
                    }

                    columns = {
                        "ltp": float(ltpc.get('ltp', 0)),
                        "ltq": int(float(ltpc.get('ltq', 0))),
                        "cp": float(ltpc.get('cp', 0)),
                        "vtt": int(float(data.get('vtt', 0))) if mode == 'marketFF' else 0,
                        "atp": float(data.get('atp', 0)) if mode == 'marketFF' else 0
                    }

                    # Using the datetime object for the 'at' parameter
                    sender.row('tick_data', symbols=symbols, columns=columns, at=dt_object)
                    
                    count += 1
                    if count % 100 == 0:
                        sender.flush()

                except Exception as e:
                    logger.error(f"Error processing record {doc.get('_id')}: {e}")
            
            sender.flush()
            logger.info(f"Successfully migrated {count} rows.")

    except Exception as e:
        logger.error(f"QuestDB Connection Error: {e}")

if __name__ == "__main__":
    migrate()