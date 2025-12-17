# =========================
# FILE: historical_data_fetcher.py
# =========================
# Fetches historical OHLC data from Upstox API and saves to MongoDB
# Required for H1 SMA 50 calculation (need 50+ H1 candles)

import requests
from datetime import datetime, timedelta
from pymongo import MongoClient
from typing import List, Dict, Optional
import time
import config


class HistoricalDataFetcher:
    """
    Fetches historical candle data from Upstox API.
    Saves to MongoDB for use by H1Aggregator.
    """
    
    BASE_URL = "https://api.upstox.com/v3"
    
    def __init__(self, access_token: str, db_name: str = config.DB_NAME):
        self.access_token = access_token
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        self.client = MongoClient(config.MONGO_URI)
        self.db = self.client[db_name]
        # h1_collection is legacy, new methods use fetch_and_save_period to generic collection
        self.h1_collection = self.db["h1_candles"]
        
        # Create index for efficient queries
        self.h1_collection.create_index([("symbol", 1), ("ts", 1)], unique=True)
    
    def fetch_historical_candles(
        self, 
        instrument_key: str, 
        interval: str = "1",  # 1 minute
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict]:
        """
        Fetch historical candles from Upstox.
        
        Args:
            instrument_key: e.g., "NSE_EQ|INE002A01018"
            interval: "1" for 1-min, "60" for 1-hour
            from_date: YYYY-MM-DD
            to_date: YYYY-MM-DD
            
        Returns:
            List of candle dicts with ts, open, high, low, close, volume
        """
        # URL encode the instrument key (| becomes %7C)
        encoded_key = instrument_key.replace("|", "%7C")
        
        # Default to last 10 days if not specified
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d")
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        
        url = f"{self.BASE_URL}/historical-candle/{encoded_key}/minutes/{interval}/{to_date}/{from_date}"
        
        try:
            response = requests.get(url, headers=self.headers)
            data = response.json()
            
            if response.status_code != 200 or data.get("status") != "success":
                print(f"Error fetching {instrument_key}: {data}")
                return []
            
            candles = []
            for c in data.get("data", {}).get("candles", []):
                # Format: [timestamp, open, high, low, close, volume, oi]
                ts_str = c[0]
                ts_ms = int(datetime.fromisoformat(ts_str).timestamp() * 1000)
                
                candles.append({
                    "ts": ts_ms,
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                    "oi": float(c[6]) if len(c) > 6 else 0
                })
            
            return sorted(candles, key=lambda x: x["ts"])
            
        except Exception as e:
            print(f"Exception fetching {instrument_key}: {e}")
            return []
    
    
    def aggregate_to_timeframe(self, candles_1m: List[Dict], timeframe_minutes: int) -> List[Dict]:
        """
        Aggregate 1-minute candles to generic timeframe candles.
        """
        if not candles_1m:
            return []
        
        aggregated_candles = []
        current_candle = None
        current_window_start = None
        
        window_size_sec = timeframe_minutes * 60
        
        for c in candles_1m:
            # Get window start (aligned to market open or simple modulo)
            ts_sec = c["ts"] // 1000
            
            # Simple aggregation aligned to hour/window
            # Ideally should align to Market Open (9:15), but simple modulus works if 9:15 is multiple
            # 9:15 is 33300 sec from midnight.
            # For 60m: 33300 % 3600 != 0. 
            # So simple division aligns to 9:00, 10:00. This handles 9:15-10:15 correctly if we use custom logic.
            # Reusing the robust logic from H1Aggregator is best, but let's stick to simple modulus for now 
            # OR copy the _get_window_start logic?
            # Let's use simple modulus aligned to 0 for now as standard OHLC bars usually align to clock.
            # 30m: 9:00, 9:30. 
            # 9:15 candle belongs to 9:00-9:30 bar. Correct.
            
            window_start = (ts_sec // window_size_sec) * window_size_sec
            
            if current_window_start != window_start:
                # Save previous if exists
                if current_candle:
                    aggregated_candles.append(current_candle)
                
                # Start new
                current_window_start = window_start
                current_candle = {
                    "ts": (window_start + window_size_sec) * 1000,  # Close time
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"]
                }
            else:
                # Update current
                current_candle["high"] = max(current_candle["high"], c["high"])
                current_candle["low"] = min(current_candle["low"], c["low"])
                current_candle["close"] = c["close"]
                current_candle["volume"] += c["volume"]
        
        # Add last
        if current_candle:
            aggregated_candles.append(current_candle)
        
        return aggregated_candles
    
    def fetch_and_save_period(self, instrument_key: str, days: int = 20, timeframe_minutes: int = 60) -> int:
        """
        Fetch historical data, aggregate to timeframe, and save to MongoDB.
        """
        print(f"Fetching {days} days of data for {instrument_key}...")
        
        # Fetch 1-minute data
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        candles_1m = self.fetch_historical_candles(
            instrument_key, 
            interval="1",
            from_date=from_date,
            to_date=to_date
        )
        
        if not candles_1m:
            print(f"No 1-min data received for {instrument_key}")
            return 0
        
        print(f"Received {len(candles_1m)} 1-min candles")
        
        # Aggregate to timeframe - Use aggregate_to_timeframe (was aggregate_to_h1)
        aggregated = self.aggregate_to_timeframe(candles_1m, timeframe_minutes)
        print(f"Aggregated to {len(aggregated)} {timeframe_minutes}-min candles")
        
        # Save to MongoDB
        collection_name = f"context_candles_{timeframe_minutes}m"
        coll = self.db[collection_name]
        
        saved = 0
        for candle in aggregated:
            ts_val = candle["ts"]
            doc = {
                "symbol": instrument_key,
                "ts": ts_val,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"]
            }
            try:
                coll.update_one(
                    {"symbol": instrument_key, "ts": ts_val},
                    {"$set": doc},
                    upsert=True
                )
                saved += 1
            except Exception as e:
                print(f"Error saving candle: {e}")
        
        print(f"Saved {saved} {timeframe_minutes}-min candles to MongoDB '{collection_name}'")
        return saved
    
    def load_h1_candles(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Load H1 candles from MongoDB for a symbol.
        """
        cursor = self.h1_collection.find(
            {"symbol": symbol},
            {"_id": 0}
        ).sort("ts", 1).limit(limit)
        
        return list(cursor)

    def calculate_5day_adv(self, symbol: str) -> float:
        """
        Calculate 5-day Average Daily Volume (ADV).
        Use last 5 completed daily candles (aggregate H1 -> D1).
        """
        # Load last 120 H1 candles (approx 5-10 days)
        h1_candles = self.load_h1_candles(symbol, limit=200)
        
        if not h1_candles:
            return 0.0
            
        # Group by day
        daily_vol = {}
        for h1 in h1_candles:
            ts_sec = h1["ts"] // 1000
            # Rough daily grouping (IST aware)
            date_str = datetime.fromtimestamp(ts_sec + 19800).strftime("%Y-%m-%d")
            daily_vol[date_str] = daily_vol.get(date_str, 0) + h1["volume"]
            
        # Get volumes for unique days
        volumes = list(daily_vol.values())
        
        # We need at least 1 day, ideally 5
        if not volumes:
            return 0.0
            
        # Take last 5 days
        recent_vols = volumes[-5:]
        adv = sum(recent_vols) / len(recent_vols)
        print(f"[ADV] {symbol} 5-day ADV: {adv:,.0f} (from {len(recent_vols)} days)")
        return adv


def backfill_all_symbols(access_token: str, symbols: List[str], days: int = 20, timeframe_minutes: int = 60):
    """
    Backfill data for all symbols for a specific bias timeframe.
    """
    fetcher = HistoricalDataFetcher(access_token)
    
    for symbol in symbols:
        try:
            count = fetcher.fetch_and_save_period(symbol, days, timeframe_minutes)
            print(f"✓ {symbol}: {count} {timeframe_minutes}m candles")
        except Exception as e:
            print(f"✗ {symbol}: {e}")
        
        # Rate limiting
        time.sleep(0.5)



if __name__ == "__main__":
    
    print("=" * 50)
    print(f"BACKFILLING DATA (Timeframe: {config.BIAS_TIMEFRAME_MINUTES}m)")
    print("=" * 50)
    
    # Use watchlist from config
    backfill_all_symbols(
        config.ACCESS_TOKEN, 
        config.WATCHLIST, 
        days=15, 
        timeframe_minutes=config.BIAS_TIMEFRAME_MINUTES
    )
    
    print(f"\nDone! candles saved to MongoDB for timeframe {config.BIAS_TIMEFRAME_MINUTES}m")
