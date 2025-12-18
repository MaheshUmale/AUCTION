# load_data.py
import json
import argparse
import gzip
from trading_core.persistence import QuestDBPersistence
from datetime import datetime

def load_data(symbol: str, file_path: str):
    """
    Loads historical tick data from a JSON file into QuestDB.
    """
    persistence = QuestDBPersistence(db_name="auction_trading_backtest")
    with gzip.open(file_path, 'rt') as f:
        data = json.load(f)
        for record in data:
            full_feed = record.get("fullFeed", {})
            market = full_feed.get("marketFF") or full_feed.get("indexFF")
            if not market:
                continue

            ltpc = market.get('ltpc')
            if ltpc and 'ltp' in ltpc and 'ltt' in ltpc:
                tick_data = {
                    'timestamp': int(ltpc['ltt']),
                    'instrument_key': symbol,
                    'feed_type': 'TICK',
                    'ltp': ltpc.get('ltp'),
                    'ltq': int(ltpc.get('ltq')) if ltpc.get('ltq') is not None else None,
                    'cp': market.get('cp'),
                    'oi': int(market.get('oi')) if market.get('oi') is not None else None,
                    'atp': market.get('atp'),
                    'vtt': int(market.get('vtt')) if market.get('vtt') is not None else None,
                    'tbq': market.get('tbq'),
                    'tsq': market.get('tsq'),
                    'insertion_time': datetime.now()
                }
                persistence.save_tick_data(tick_data)

def main():
    """Main function to run the data loader."""
    parser = argparse.ArgumentParser(description="Load historical tick data into QuestDB.")
    parser.add_argument("--symbol", type=str, required=True, help="The symbol to load data for.")
    parser.add_argument("--file", type=str, required=True, help="The path to the JSON data file.")
    args = parser.parse_args()

    load_data(args.symbol, args.file)

if __name__ == "__main__":
    main()
