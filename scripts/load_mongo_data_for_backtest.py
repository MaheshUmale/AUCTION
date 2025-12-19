# scripts/load_mongo_data_for_backtest.py

import sys
import os
from datetime import datetime, timedelta

# Add project root to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient
import logging

# Local imports
from trading_core.persistence import QuestDBPersistence
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
MONGO_URI = config.MONGO_URI
MONGO_DB_NAME = "upstox_strategy_db"
TICK_COLLECTION_NAME = "tick_data"

QUESTDB_DB_NAME = config.DB_NAME

def parse_mongo_tick(mongo_doc):
    """
    Parses a tick document from MongoDB and transforms it into the format
    expected by QuestDBPersistence.save_market_data.
    """
    try:
        instrument_key = mongo_doc.get("instrumentKey")
        full_feed = mongo_doc.get("fullFeed", {})
        market_ff = full_feed.get("marketFF", {})
        ltpc = market_ff.get("ltpc", {})
        market_level = market_ff.get("marketLevel", {})

        # Handle cases where ohlc data might be missing or empty
        ohlc_list = market_ff.get("marketOHLC", {}).get("ohlc", [])
        ohlc_data = ohlc_list[0] if ohlc_list else {}

        bid_ask_quote = market_level.get("bidAskQuote", [{}])

        # Validate essential fields
        if not instrument_key or not ltpc.get("ltt"):
            return None

        timestamp_ms = int(ltpc.get("ltt"))
        insertion_time_dt = mongo_doc.get("_insertion_time")

        # Basic data mapping
        data = {
            'timestamp': datetime.fromtimestamp(timestamp_ms / 1000.0),
            'instrument_key': instrument_key,
            'feed_type': 'TICK_DATA',
            'ltp': float(ltpc.get('ltp')) if ltpc.get('ltp') is not None else None,
            'ltt': timestamp_ms,
            'ltq': int(ltpc.get('ltq')) if ltpc.get('ltq') is not None else None,
            'cp': float(ltpc.get('cp')) if ltpc.get('cp') is not None else None,
            'vtt': int(market_ff.get('vtt')) if market_ff.get('vtt') is not None else None,
            'tbq': float(market_ff.get('tbq')) if market_ff.get('tbq') is not None else None,
            'tsq': float(market_ff.get('tsq')) if market_ff.get('tsq') is not None else None,
            'oi': None,
            'atp': None,
            'delta': None, 'theta': None, 'gamma': None, 'vega': None, 'rho': None, 'iv': None,
            'open': float(ohlc_data.get('open')) if ohlc_data.get('open') is not None else None,
            'high': float(ohlc_data.get('high')) if ohlc_data.get('high') is not None else None,
            'low': float(ohlc_data.get('low')) if ohlc_data.get('low') is not None else None,
            'close': float(ohlc_data.get('close')) if ohlc_data.get('close') is not None else None,
            'insertion_time': insertion_time_dt,
        }

        # Market depth (Level 1)
        if bid_ask_quote and len(bid_ask_quote) > 0:
            level1 = bid_ask_quote[0]
            data.update({
                'bid_price_1': float(level1.get('bidP')) if level1.get('bidP') is not None else None,
                'bid_qty_1': int(level1.get('bidQ')) if level1.get('bidQ') is not None else None,
                'ask_price_1': float(level1.get('askP')) if level1.get('askP') is not None else None,
                'ask_qty_1': int(level1.get('askQ')) if level1.get('askQ') is not None else None,
            })
        else:
             data.update({
                'bid_price_1': None, 'bid_qty_1': None,
                'ask_price_1': None, 'ask_qty_1': None
            })

        return data
    except (ValueError, TypeError, IndexError) as e:
        logging.error(f"Error parsing document with _id {mongo_doc.get('_id')}: {e}")
        return None

def load_data_from_mongo_to_questdb():
    """
    Main function to connect to MongoDB, fetch recent tick data,
    and load it into QuestDB.
    """
    logging.info("Starting data load from MongoDB to QuestDB...")

    # --- Connect to Databases ---
    try:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client[MONGO_DB_NAME]
        tick_collection = mongo_db[TICK_COLLECTION_NAME]
        logging.info("Successfully connected to MongoDB.")
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        return

    try:
        qdb_persistence = QuestDBPersistence(db_name=QUESTDB_DB_NAME)
        logging.info("Successfully connected to QuestDB.")
    except Exception as e:
        logging.error(f"Failed to connect to QuestDB: {e}")
        return

    # --- Fetch Data and Load ---
    try:
        logging.info("Fetching distinct instrument keys from MongoDB...")
        symbols = tick_collection.distinct("instrumentKey")
        logging.info(f"Found {len(symbols)} symbols to process.")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)

        total_docs_processed = 0

        for i, symbol in enumerate(symbols):
            logging.info(f"Processing symbol {i+1}/{len(symbols)}: {symbol}")

            query = {
                "instrumentKey": symbol,
                "_insertion_time": {
                    "$gte": start_date,
                    "$lt": end_date
                }
            }

            cursor = tick_collection.find(query)
            docs_for_symbol = 0
            for doc in cursor:
                parsed_data = parse_mongo_tick(doc)
                if parsed_data:
                    try:
                        qdb_persistence.save_market_data(parsed_data)
                        docs_for_symbol += 1
                    except Exception as e:
                        logging.error(f"Failed to save data for {symbol} to QuestDB: {e}")
                        logging.debug(f"Problematic data: {parsed_data}")

            logging.info(f"Processed {docs_for_symbol} documents for {symbol}.")
            total_docs_processed += docs_for_symbol

        logging.info(f"\n--- Data Load Complete ---")
        logging.info(f"Total documents processed: {total_docs_processed}")

    except Exception as e:
        logging.error(f"An error occurred during the data load process: {e}")
    finally:
        mongo_client.close()
        logging.info("MongoDB connection closed.")

if __name__ == "__main__":
    load_data_from_mongo_to_questdb()
