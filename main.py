
from models import Tick
from saveChart import savePlotlyHTML, plotMe
import csv
import gzip
import json
from datetime import datetime, timezone
from pymongo import MongoClient
import pandas as pd
from stage8_engine import LiveAuctionEngine, LiveMarketRouter
from models import Trade

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["upstox_strategy_db"]
tick_collection = db["tick_data"]

def get_symbols_from_today():
    """Returns a list of symbols for today's trading session."""
    return [
        "NSE_FO|51502", "NSE_EQ|INE01EA01019", "NSE_FO|51461", "NSE_FO|60166",
        "NSE_EQ|INE465A01025", "NSE_EQ|INE118H01025", "NSE_FO|51460", "NSE_FO|51414",
        "NSE_FO|51420", "NSE_FO|51498", "NSE_EQ|INE811K01011", "NSE_EQ|INE027H01010"
    ]

def get_trades_from_today(symbol: str):
    """Fetches closed trades for a given symbol from MongoDB."""
    client = MongoClient('mongodb://localhost:27017/')
    result = client['auction_trading']['closed_trades'].find({"symbol": symbol}, {"_id": 0})
    return [Trade(**doc) for doc in result]

def simulate_live_ticks_to_router(instrument_key: str, router: LiveMarketRouter):
    """Simulates live tick data from a .gz file and sends it to the router."""
    print(f"Simulating data for instrument: {instrument_key}")
    output_filename = f"{instrument_key.replace('|', '_')}_data.json.json.gz"

    try:
        with gzip.open(output_filename, 'rt', encoding='utf-8') as f:
            records = json.load(f)
            for record in records:
                inst = {f'{instrument_key}': record}
                feed = {"feeds": inst}
                router.on_message(feed)
    except FileNotFoundError:
        print(f"Error: Data file not found at {output_filename}")
    except Exception as e:
        print(f"An error occurred while processing the data file: {e}")

def main():
    """Main function to run the backtesting process."""
    engine = LiveAuctionEngine()
    router = LiveMarketRouter(engine)

    instruments = get_symbols_from_today()

    for symbol in instruments:
        simulate_live_ticks_to_router(symbol, router)

        # Since the engine processes data in-memory, we can retrieve trades directly
        trades = get_trades_from_today(symbol)

        if trades:
            # Assuming plotMe and other analysis functions are defined elsewhere
            # plotMe(symbol, candles_1m, trades)
            print(f"Found {len(trades)} trades for {symbol}")
            summarize(trades)

def summarize(trades):
    """Summarizes the performance of a list of trades."""
    if not trades:
        print("No trades to summarize.")
        return

    df = pd.DataFrame([{
        "side": t.side,
        "pnl": t.exit_price - t.entry_price if t.side == "LONG" else t.entry_price - t.exit_price
    } for t in trades]).dropna()

    if not df.empty:
        print("\n===== Trade Summary =====")
        print(df.groupby("side")[["pnl"]].mean())
    else:
        print("No valid trades to summarize.")

if __name__ == "__main__":
    main()
