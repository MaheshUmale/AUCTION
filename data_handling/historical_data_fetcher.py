# =========================
# FILE: historical_data_fetcher.py
# =========================
# Fetches historical OHLC data from Upstox API and uses the persistence layer to save it.

import requests
from datetime import datetime, timedelta
from typing import List, Dict
import config
from trading_core.persistence import QuestDBPersistence
from trading_core.models import Candle

class HistoricalDataFetcher:
    """
    Fetches historical candle data from Upstox API and provides methods
    to load and save it via the provided persistence layer.
    """
    
    BASE_URL = "https://api.upstox.com/v3"
    
    def __init__(self, access_token: str, persistence: QuestDBPersistence):
        self.access_token = access_token
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        self.persistence = persistence
    
    def fetch_historical_candles(
        self, 
        instrument_key: str, 
        interval: str = "1",
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict]:
        """
        Fetches historical candles from Upstox.
        """
        encoded_key = instrument_key.replace("|", "%7C")
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
                ts_str = c[0]
                ts_ms = int(datetime.fromisoformat(ts_str).timestamp() * 1000)
                candles.append({
                    "ts": ts_ms, "open": float(c[1]), "high": float(c[2]),
                    "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]),
                    "oi": float(c[6]) if len(c) > 6 else 0
                })
            return sorted(candles, key=lambda x: x["ts"])
        except Exception as e:
            print(f"Exception fetching {instrument_key}: {e}")
            return []

    def aggregate_to_timeframe(self, candles_1m: List[Dict], timeframe_minutes: int) -> List[Dict]:
        """
        Aggregates 1-minute candles to a specified timeframe.
        """
        if not candles_1m:
            return []
        
        aggregated_candles = []
        current_candle = None
        current_window_start = None
        window_size_sec = timeframe_minutes * 60
        
        for c in candles_1m:
            ts_sec = c["ts"] // 1000
            window_start = (ts_sec // window_size_sec) * window_size_sec
            
            if current_window_start != window_start:
                if current_candle:
                    aggregated_candles.append(current_candle)
                
                current_window_start = window_start
                current_candle = {
                    "ts": (window_start + window_size_sec) * 1000,
                    "open": c["open"], "high": c["high"], "low": c["low"],
                    "close": c["close"], "volume": c["volume"]
                }
            else:
                current_candle["high"] = max(current_candle["high"], c["high"])
                current_candle["low"] = min(current_candle["low"], c["low"])
                current_candle["close"] = c["close"]
                current_candle["volume"] += c["volume"]
        
        if current_candle:
            aggregated_candles.append(current_candle)
        
        return aggregated_candles

    def fetch_and_save_period(self, instrument_key: str, days: int = 20, timeframe_minutes: int = 60) -> int:
        """
        Fetches, aggregates, and saves historical data for a specified period.
        """
        print(f"Fetching {days} days of data for {instrument_key} for {timeframe_minutes}m timeframe...")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        candles_1m = self.fetch_historical_candles(instrument_key, interval="1", from_date=from_date)
        
        if not candles_1m:
            print(f"No 1-min data received for {instrument_key}")
            return 0
        
        aggregated = self.aggregate_to_timeframe(candles_1m, timeframe_minutes)
        print(f"Aggregated to {len(aggregated)} {timeframe_minutes}-min candles")
        
        saved_count = self.persistence.save_context_candles(instrument_key, aggregated, timeframe_minutes)
        print(f"Saved {saved_count} {timeframe_minutes}-min candles via persistence layer.")
        return saved_count

    def load_h1_candles(self, symbol: str,BIAS_TIMEFRAME_MINUTES, limit: int = 100) -> List[Candle]:
        """
        Loads H1 (60min) candles from the persistence layer.
        """
        candles_data = self.persistence.load_context_candles(symbol,BIAS_TIMEFRAME_MINUTES , limit)
        return [Candle(**c) for c in candles_data]

    def calculate_5day_adv(self, symbol: str) -> float:
        """
        Calculates the 5-day Average Daily Volume.
        """
        h1_candles = self.load_h1_candles(symbol,config.BIAS_TIMEFRAME_MINUTES, limit=200)
        if not h1_candles:
            print(f"ADV calculation for {symbol} skipped: No H1 candles found.")
            return 0.0
            
        daily_vol = {}
        for h1 in h1_candles:
            date_str = datetime.fromtimestamp(h1.ts / 1000).strftime("%Y-%m-%d")
            daily_vol[date_str] = daily_vol.get(date_str, 0) + h1.volume
            
        volumes = list(daily_vol.values())
        if not volumes:
            return 0.0
            
        # Ignore current partial day
        last_day = datetime.fromtimestamp(h1_candles[-1].ts / 1000).strftime("%Y-%m-%d")
        is_today = last_day == datetime.now().strftime("%Y-%m-%d")

        recent_vols = volumes[-6:-1] if is_today and len(volumes) > 5 else volumes[-5:]

        if not recent_vols:
            return 0.0

        adv = sum(recent_vols) / len(recent_vols)
        print(f"[ADV] {symbol} 5-day ADV: {adv:,.0f} (from {len(recent_vols)} days)")
        return adv
