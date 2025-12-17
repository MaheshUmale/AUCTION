from models import Tick
from saveChart import savePlotlyHTML, plotMe
import csv
import gzip
import json
from datetime import datetime, timezone
from pymongo import MongoClient
import pandas as pd
import numpy as np
from stage8_engine import LiveAuctionEngine, LiveMarketRouter
from models import Trade
import pytz
import os
import sys


import config

from persistence import QuestDBPersistence

# Connect to QuestDB
persistence = QuestDBPersistence(db_name="auction_trading_backtest")

# The following lines are removed as they are MongoDB-specific
# client = MongoClient("mongodb://localhost:27017")
# db = client["upstox_strategy_db"]
# tick_collection = db["tick_data"]
# client.drop_database("auction_trading_backtest")
# print("Dropped 'auction_trading_backtest' database for clean backtest.")

def get_symbols_from_today():
    """Returns a list of symbols for today's trading session."""
    return config.WATCHLIST

def get_trades_from_today(symbol: str):
    """Fetches closed trades for a given symbol from QuestDB."""
    trades = persistence.load_closed_trades()
    return [Trade(**trade) for trade in trades if trade['symbol'] == symbol]

def simulate_live_ticks_to_router(
    instrument_key: str,
    router: LiveMarketRouter
):
    print("simulate PROCESSING --- instrument_key " + instrument_key)
    # Get a list of .gz files in the data directory
    gz_files = [f for f in os.listdir('data') if f.endswith('.gz')]
    for file in gz_files:
        with gzip.open(os.path.join('data', file), 'rt') as f:
            for line in f:
                try:
                    # Parse the JSON from the line
                    record = json.loads(line.strip())
                    # The rest of your processing logic
                    if record.get("feeds") and record["feeds"].get(instrument_key):
                        router.on_message(record)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")


ACCESS_TOKEN = config.ACCESS_TOKEN


BASE_URL = config.BASE_URL
import requests
def fetch_upstox_intraday(instrument_key: str):
    """
    Fetches 1-minute intraday candles from Upstox.
    """
    toDate = "2025-12-17"
    fromDate = "2025-12-16" # Fetch specifically Dec 16
    url = f"{BASE_URL}/historical-candle/{instrument_key}/minutes/1/{toDate}/{fromDate}" 
  
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try :
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if resp.status_code != 200 or data.get("status") != "success":
            print(f"Error fetching data for {instrument_key}: {resp.status_code}")
            print(resp.json())
            # Raise a more specific exception or handle gracefully
            return pd.DataFrame() # Return empty DF on failure
            
    
        candles_1m = parse_upstox_candles(data, 60)
        if candles_1m.empty:
            return candles_1m
            
        candles = normalize_candle_ts(candles_1m)
        return candles
    
    except Exception as e:
        import traceback
        print(f"An exception occurred while fetching/parsing Upstox data: {e}")
        traceback.print_exc()
        return pd.DataFrame() # Return empty DF on exception



import pandas as pd
from datetime import datetime, timezone
# Removed import pytz here, as datetime.timezone is sufficient for UTC/ISO parsing

def parse_upstox_candles(candle_json: dict, interval_sec: int) -> pd.DataFrame:
    rows = []

    for c in candle_json["data"]["candles"]:
        # Parse ISO timestamp with timezone. The Upstox timestamp is the START of the candle.
        # datetime.fromisoformat correctly handles the timezone in the string (e.g., '+05:30').
        # .timestamp() returns the Unix epoch in seconds (float).
        # We multiply by 1000 to get milliseconds (ms).
        ts_start_ms = int(
            datetime.fromisoformat(c[0]).timestamp() * 1000
        )

        # The 'ts' column should be the CLOSE time of the candle, in milliseconds.
        ts_close_ms = ts_start_ms + interval_sec * 1000

        rows.append({
            "ts": ts_close_ms,        # USE CLOSE TIME in milliseconds (ms)
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
            "oi": float(c[6])
        })

    return pd.DataFrame(rows)



def normalize_candle_ts(candles: pd.DataFrame) -> pd.DataFrame:
    df = candles.copy()

    # 'ts' is already an integer in milliseconds from parse_upstox_candles, so this check and conversion is redundant
    # but kept for robustness if 'ts' were a different type later.
    if not np.issubdtype(df["ts"].dtype, np.integer):
        # The original code was converting to ns ('// 1_000_000'), which is incorrect.
        # If 'ts' were a datetime object, converting to ms is:
        df["ts"] = pd.to_datetime(df["ts"]).astype("int64") // 1_000_000 # This line is potentially still problematic if it was converting from a datetime string/object.
        # Since we are ensuring 'ts' is already an integer ms timestamp, we can skip this conversion block if needed.
        pass

    return df.sort_values("ts").reset_index(drop=True)

def main():
    """Main function to run the backtesting process."""
    print(" STAGE 8 ENGINE INITIALIZE ")
    # User requested configurable timeframe from config.py
    engine = LiveAuctionEngine(
        simulation_mode=True, 
        bias_timeframe_minutes=config.BIAS_TIMEFRAME_MINUTES,
        persistence_db_name="auction_trading_backtest"
    )
    engine.loadFromDb()
    router = LiveMarketRouter(engine)

    instruments = get_symbols_from_today()

    for symbol in instruments:
        try:
            simulate_live_ticks_to_router(symbol, router)
     
            trades = get_trades_from_today(symbol)
     
            ohlc_data = fetch_upstox_intraday(symbol)
            
            if ohlc_data.empty:
                print(f"Skipping plotting for {symbol}: OHLC data is empty or failed to load.")
                continue
                
            print(ohlc_data.tail())
            
            if trades:
                print(f"Plotting for {symbol}...")
                plotMe(symbol, ohlc_data, trades)
                summarize(trades)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            # Continue to next instrument

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
    # df = fetch_upstox_intraday("NSE_EQ|INE931S01010")
    # print(df)