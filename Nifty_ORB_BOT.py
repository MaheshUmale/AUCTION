import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime, time as dt_time

# --- CONFIGURATION ---
SYMBOL = "NIFTY"
TIMEFRAME = "5min"
RANGE_END_TIME = dt_time(9, 45)  # 30-minute ORB
MAX_RISK_PERCENT = 0.15          # 15% Stop Loss
TARGET_RR = 1.5                  # 1:1.5 Risk Reward

class NiftyORBBot:
    def __init__(self):
        self.range_high = None
        self.range_low = None
        self.is_trade_active = False
        self.entry_price = 0
        self.sl_price = 0

    def fetch_nse_option_chain(self):
        """Fetches and calculates the Change in OI Ratio."""
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={SYMBOL}"
        headers = {'User-Agent': 'Mozilla/5.0'} 
        # Note: In a real bot, use a session with cookies to avoid 403 errors
        try:
            data = requests.get(url, headers=headers).json()
            records = data['filtered']['data']
            
            # Calculate Change in OI for ATM +/- 2 strikes
            atm_strike = data['records']['underlyingValue']
            # Rounding logic for Nifty
            atm_price = round(atm_strike / 50) * 50
            
            sum_ce_change_oi = 0
            sum_pe_change_oi = 0
            
            for strike in records:
                if abs(strike['strikePrice'] - atm_price) <= 100:
                    sum_ce_change_oi += strike['CE']['changeinOpenInterest']
                    sum_pe_change_oi += strike['PE']['changeinOpenInterest']
            
            oi_ratio = sum_pe_change_oi / sum_ce_change_oi if sum_ce_change_oi != 0 else 0
            return oi_ratio
        except:
            return 1.0 # Neutral if data fails

    def check_consolidation(self, df):
        """Checks if the last 3 candles are within 0.15% of the range boundary."""
        last_3 = df.tail(3)
        # For Bullish: Check if Highs are near self.range_high
        is_tight = all(abs(last_3['high'] - self.range_high) / self.range_high < 0.0015)
        # Check if candles are above 20 EMA
        above_ema = all(last_3['close'] > last_3['ema20'])
        return is_tight and above_ema

    def execute_logic(self):
        # 1. GET DATA (Using placeholder for Index & Option OHLC)
        df = self.get_market_data(SYMBOL) # Custom function to get 5min candles
        df['ema20'] = ta.ema(df['close'], length=20)
        
        current_time = datetime.now().time()
        current_price = df['close'].iloc[-1]

        # 2. DEFINE THE BOX (09:15 - 09:45)
        if current_time == RANGE_END_TIME:
            morning_data = df.between_time('09:15', '09:45')
            self.range_high = morning_data['high'].max()
            self.range_low = morning_data['low'].min()
            print(f"Range Defined: {self.range_low} - {self.range_high}")

        # 3. ENTRY SCANNER (Only if no active trade)
        if not self.is_trade_active and self.range_high:
            oi_ratio = self.fetch_nse_option_chain()
            
            # BULLISH CONDITION
            if current_price > self.range_high:
                if self.check_consolidation(df) and oi_ratio > 1.5:
                    self.enter_trade(type="CE", price=current_price)

            # BEARISH CONDITION
            elif current_price < self.range_low:
                if self.check_consolidation(df) and oi_ratio < 0.6:
                    self.enter_trade(type="PE", price=current_price)

    def enter_trade(self, type, price):
        print(f"ENTERING {type} at {price}")
        self.is_trade_active = True
        self.entry_price = price 
        # SL is the low of the breakout candle
        self.sl_price = price * (1 - 0.15) if type == "CE" else price * (1 + 0.15)
        # Execute Order via Broker API here
        # broker.place_order(symbol=ATM_STRIKE, side="BUY"...)

    def manage_exit(self, current_price):
        """Calculates Target and Trailing SL."""
        # Target 1: 1.5 RR
        target_price = self.entry_price + (self.entry_price - self.sl_price) * TARGET_RR
        
        if current_price >= target_price:
            print("Target Hit! Booking 50% and Trailing to Cost.")
            # Move SL to Entry
            self.sl_price = self.entry_price
            
        if current_price <= self.sl_price:
            print("Stop Loss Hit. Exiting.")
            self.is_trade_active = False

# --- MAIN LOOP ---
bot = NiftyORBBot()
while True:
    bot.execute_logic()
    time.sleep(60) # Run every minute
    