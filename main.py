
from models  import Tick 

from saveChart import savePlotlyHTML, plotMe
import csv






from pymongo import MongoClient
import pandas as pd
import numpy as np
client = MongoClient("mongodb://localhost:27017")
db = client["upstox_strategy_db"]
tick_collection = db["tick_data"]

from datetime import datetime, tzinfo, timezone
from pymongo import MongoClient
from datetime import datetime, timedelta

def processLiveDB():
    MongoClient("mongodb://localhost:27017")
    db = client["upstox_data"]
    collection = db["live_feed"]

def getSymbolsFromToday():
    todaysSymbols=["NSE_FO|51502","NSE_EQ|INE01EA01019","NSE_FO|51461","NSE_FO|60166","NSE_EQ|INE465A01025","NSE_EQ|INE118H01025","NSE_FO|51460","NSE_FO|51414","NSE_FO|51420","NSE_FO|51498","NSE_EQ|INE811K01011","NSE_EQ|INE027H01010","NSE_EQ|INE584A01023","NSE_FO|51421","NSE_FO|51417","NSE_FO|51476","NSE_FO|51493","NSE_FO|51507","NSE_EQ|INE466L01038","NSE_EQ|INE849A01020","NSE_FO|51421","NSE_EQ|INE027H01010","NSE_FO|51476","NSE_FO|51493","NSE_EQ|INE584A01023","NSE_FO|51502","NSE_EQ|INE01EA01019","NSE_EQ|INE118H01025","NSE_EQ|INE465A01025","NSE_FO|51510","NSE_FO|51507","NSE_FO|51460","NSE_FO|51420","NSE_FO|51498"]
    return todaysSymbols

from dataclasses import dataclass

from dataclasses import dataclass
from typing import Optional

# @dataclass
# class Trade:
#     symbol: str
#     side: str
#     entry_price: float
#     entry_ts: int
#     exit_price: Optional[float] = None
#     exit_ts: Optional[int] = None
#     reason: Optional[str] = None

from dataclasses import dataclass
from typing import Optional

from models import *
from pymongo import MongoClient

from dataclasses import asdict
def getTradesFromToday(symbol):


    # Requires the PyMongo package.
    # https://api.mongodb.com/python/current
    client = MongoClient('mongodb://localhost:27017/')
 
    result = client['auction_trading']['closed_trades'].find(
    {"symbol": symbol},{"_id": 0}
    )
    trades =[]

    for docObj in result :
        print(docObj)
        doc = Trade(**docObj)
        
        trades.append(doc)

    # for trade in trades :
    #     if trade.side=="LONG" :
    #         print("long")
    #     print(trade.side)

    # return []
    return trades
 
import gzip
import json

def simulateLiveTicksToRouter(
    instrument_key: str,
    startDate :str,
    endDate:str,
)  :
    
    print("simulate PROCESSING --- instrument_key "+instrument_key)
    
    # The format code '%Y-%m-%d' matches the 'yyyy-mm-dd' string format
    datetime_start = datetime.strptime(endDate, '%Y-%m-%d')
    # To add the UTC timezone information, use .replace()
    startDate_utc = datetime_start.replace(tzinfo=timezone.utc)

    # The format code '%Y-%m-%d' matches the 'yyyy-mm-dd' string format
    datetime_end = datetime.strptime(startDate, '%Y-%m-%d')
    # To add the UTC timezone information, use .replace()
    endDate_utc = datetime_end.replace(tzinfo=timezone.utc)


    
    # 1. Convert strings to Python datetime objects for precise time handling
    start_of_day = datetime.strptime(startDate + "T00:00:00.000", "%Y-%m-%dT%H:%M:%S.%f")
    # For the end date, parse the start of that day and add almost 24 hours (one full day minus a millisecond for precision)
    # A safer way to handle 'endDate' might be to assume it's also a single day, or use the next day's start time for the $lt boundary.
    end_of_day = datetime.strptime(endDate + "T23:59:59.999", "%Y-%m-%dT%H:%M:%S.%f")

 

    # 2. Pass the native datetime objects to the PyMongo query
    cursor = tick_collection.find(
        {
            "instrumentKey": instrument_key,
            "_insertion_time": {
                "$gte": start_of_day, # Pass the datetime object directly
                "$lt": end_of_day      # Pass the datetime object directly
            }
        },
        {

            "_id": 0
        }
    ).sort("_insertion_time", 1) 
    list_cursor = list(cursor)

    # for doc in list_cursor:      
    #     inst ={f'{instrument_key}': doc}
    #     feed ={"feeds":inst}  
    #     router.on_message(feed)
        

    # Prepare data for JSON serialization (convert cursor to a list)
    # Note: PyMongo returns BSON objects, which need careful conversion for extended JSON types


    
    output_file = instrument_key.replace("|","_")+"_data.json"

    # Save results to a GZIP compressed JSON file
    output_filename = output_file+'.json.gz'
    with gzip.open(output_filename, 'wt', encoding='utf-8') as f:
        # 'wt' mode opens the file for writing text to a compressed stream
        json.dump(list_cursor, f, default=str, indent=4) 

    print(f"Exported {len(list_cursor)} documents to {output_filename}")

    # # Write the data to a JSON file
    # try:
    #     with open(output_file, 'w') as f:
    #         # Use json.dump for a standard JSON array format
    #         json.dump(list_cursor, f, indent=4, default=str) # Use default=str to handle ObjectIds/dates
    #     print(f"Successfully exported {len(list_cursor)} records to {output_file}")
    # except IOError as e:
    #     print(f"Error writing to file: {e}")

    # Close the connection
    # client.close()


  
import json
 


def generate_tick_df(
    instrument_key: str,
    startDate :str,
    endDate:str,
) -> pd.DataFrame:

   
    # The format code '%Y-%m-%d' matches the 'yyyy-mm-dd' string format
    datetime_start = datetime.strptime(endDate, '%Y-%m-%d')
    # To add the UTC timezone information, use .replace()
    startDate_utc = datetime_start.replace(tzinfo=timezone.utc)

    # The format code '%Y-%m-%d' matches the 'yyyy-mm-dd' string format
    datetime_end = datetime.strptime(startDate, '%Y-%m-%d')
    # To add the UTC timezone information, use .replace()
    endDate_utc = datetime_end.replace(tzinfo=timezone.utc)


    
    # 1. Convert strings to Python datetime objects for precise time handling
    start_of_day = datetime.strptime(startDate + "T00:00:00.000", "%Y-%m-%dT%H:%M:%S.%f")
    # For the end date, parse the start of that day and add almost 24 hours (one full day minus a millisecond for precision)
    # A safer way to handle 'endDate' might be to assume it's also a single day, or use the next day's start time for the $lt boundary.
    end_of_day = datetime.strptime(endDate + "T23:59:59.999", "%Y-%m-%dT%H:%M:%S.%f")

 

    # 2. Pass the native datetime objects to the PyMongo query
    cursor = tick_collection.find(
        {
            "instrumentKey": instrument_key,
            "_insertion_time": {
                "$gte": start_of_day, # Pass the datetime object directly
                "$lt": end_of_day      # Pass the datetime object directly
            }
        },
        {
            "fullFeed.marketFF.ltpc": 1,
            "fullFeed.marketFF.marketLevel.bidAskQuote": 1,
            "fullFeed.marketFF.atp": 1,
            "fullFeed.marketFF.tsq": 1,
            "fullFeed.marketFF.tbq": 1,
            "fullFeed.marketFF.oi": 1,


            "_id": 0
        }
    ).sort("fullFeed.marketFF.ltpc.ltt", 1)

    # Iterate over the results
    


    rows = []
    last_side = None

    for doc in cursor:
        ff = doc["fullFeed"]["marketFF"]

        ltp = float(ff["ltpc"]["ltp"])
        ltt = int(ff["ltpc"]["ltt"])
        ltq = float(ff["ltpc"]["ltq"])
        # print(ff)
        atp = float(ff.get("atp", '0.0'))   
        tbq = float(ff.get("tbq", '0.0'))   
        tsq = float(ff.get("tsq", '0.0'))   
        oi = float(ff.get("oi", '0.0'))   
 


        quotes = ff.get("marketLevel", {}).get("bidAskQuote", [])
        if not quotes:
            continue

        best_bid = float(quotes[0].get("bidP", '0.0'))
        best_ask = float(quotes[0].get("askP", '0.0'))

        # Side inference
        if ltp >= best_ask:
            side = "B"
        elif ltp <= best_bid:
            side = "S"
        else:
            side = last_side  # fallback

        last_side = side

        rows.append({
            "ts": int(ltt),
            "price": float(ltp),
            "volume": float(ltq),
            "side": str(side),
            "atp" : float(atp),
            "tbq" : float(tbq),
            "tsq" : float(tsq),
            "oi" : float(oi),
            
        }),
        

    df = pd.DataFrame(rows)
    return df




import pandas as pd
from datetime import datetime
import pytz

def parse_upstox_candles(candle_json: dict, interval_sec: int) -> pd.DataFrame:
    rows = []

    for c in candle_json["data"]["candles"]:
        # Parse ISO timestamp with timezone
        ts_start = int(
            datetime.fromisoformat(c[0]).timestamp() * 1000
        )

        ts_close = ts_start + interval_sec * 1000

        rows.append({
            "ts": ts_close,        # USE CLOSE TIME
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
            "oi": float(c[6])
        })

    return pd.DataFrame(rows)


UPSTOX_ACCESS_TOKEN= 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTNlMzQ1ODZkOTUwZjdjMDVhY2JlZGQiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NTY4NDMxMiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY1NzQ5NjAwfQ.VpdHs2PhvDiAMSjjjmxi5OR3A0z__si0ADnleHEd4Og'


BASE_URL = "https://api.upstox.com/v3"
import requests
def fetch_upstox_intraday(instrument_key: str):
    """
    curl --location 'https://api.upstox.com/v3/historical-candle/intraday/NSE_EQ%7CINE848E01016/minutes/1' \
--header 'Content-Type: application/json' \
--header 'Accept: application/json' \
--header 'Authorization: Bearer {your_access_token}'
    URL format:
    /historical-candle/:instrument_key/:interval/:to_date/:from_date
    Dates must be YYYY-MM-DD
    """
    url = f"{BASE_URL}/historical-candle/intraday/{instrument_key}/minutes/1" 
  
    # print(url)
    headers = {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    # print(headers)
    try :
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if resp.status_code != 200 or data.get("status") != "success":
            print(resp)
            print(resp.json())
            raise Exception(f"Upstox error: {resp}") 
            
    
        candles_1m = parse_upstox_candles(data, 60)
        candles = normalize_candle_ts(candles_1m)
        return candles
    
    except :
        import traceback
        traceback.print_exc()

    
def fetch_upstox_historical(instrument_key: str,unit:str, interval: int, start_date: str, end_date: str):
    """
    Upstox V2 historical candles API.
    URL format:
    /historical-candle/:instrument_key/:interval/:to_date/:from_date
    Dates must be YYYY-MM-DD
    """
    intraday_url = f"{BASE_URL}/historical-candle/intraday/{instrument_key}/1minute" 
    url = f"{BASE_URL}/historical-candle/{instrument_key}/{unit}/{interval}/{end_date}/{start_date}"
     
    # print(url)
    headers = {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    # print(headers)
    try :
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if resp.status_code != 200 or data.get("status") != "success":
            print(resp)
            print(resp.json())
            raise Exception(f"Upstox error: {resp}") 
            
        return data
    
    except :
        import traceback
        traceback.print_exc()


def tick_df_to_objects(tick_df: pd.DataFrame):
    ticks = []

    for _, r in tick_df.iterrows():
        ticks.append(
            Tick(
                ts=int(r["ts"]),
                price=float(r["price"]),
                volume=float(r["volume"]),
                side = 1 if r["side"] in ("B", "BUY") else (-1 if r["side"] in ("S", "SELL") else 0) ,
                # atp=float(r.get("atp", 0.0)),
                # tbq=float(r.get("tbq", 0.0)),
                # tsq=float(r.get("tsq", 0.0)),
                # oi=float(r.get("oi", 0.0)),
            )
        )
    return ticks


def normalize_candle_ts(candles: pd.DataFrame) -> pd.DataFrame:
    df = candles.copy()

    if not np.issubdtype(df["ts"].dtype, np.integer):
        df["ts"] = pd.to_datetime(df["ts"]).astype("int64") // 1_000_000

    return df.sort_values("ts").reset_index(drop=True)

def getUpstoxCandleDataAndNormalizeTS(symbol , startDate, endDate, timeunit="minutes",interval=1):
    responseJSON = fetch_upstox_historical(symbol,timeunit,interval , startDate, endDate, isIntradayToday=True)
    candles =None
    if responseJSON:
        # print(responseJSON)
        candles_1m = parse_upstox_candles(responseJSON, 60*interval)
        candles = normalize_candle_ts(candles_1m)

    return candles
 
def main():


    # instrumentsAll = ["NSE_EQ|INE081A01020","NSE_EQ|INE646L01027","NSE_EQ|INE009A01021","NSE_EQ|INE118H01025","NSE_EQ|INE237A01028","NSE_EQ|INE002A01018","NSE_EQ|INE267A01025","NSE_EQ|INE062A01020","NSE_EQ|INE040A01034","NSE_FO|51475","NSE_EQ|INE758T01015","NSE_EQ|INE205A01025","NSE_EQ|INE018A01030","NSE_EQ|INE935N01020","NSE_EQ|INE397D01024","NSE_FO|51476","NSE_FO|51415","NSE_EQ|INE090A01021","NSE_FO|60166","NSE_FO|51460","NSE_FO|51461","NSE_FO|51439","NSE_FO|51440","NSE_EQ|INE263A01024","NSE_EQ|INE101A01026","NSE_EQ|INE028A01039","NSE_EQ|INE030A01027","NSE_FO|51421"]
    #6 trendy 6 sideways
    instruments_trending =["NSE_EQ|INE267A01025","NSE_EQ|INE028A01039","NSE_EQ|INE205A01025","NSE_EQ|INE935N01020","NSE_EQ|INE758T01015","NSE_EQ|INE118H01025"]
    instruments_Nontrending= ["NSE_EQ|INE018A01030","NSE_EQ|INE030A01027","NSE_EQ|INE081A01020","NSE_EQ|INE646L01027","NSE_EQ|INE040A01034","NSE_EQ|INE009A01021"]
    
    field_names=[ 'symbol', 'entry_ts','entry_price',"mae","mfe",'exit_reason', 'side'  ,'stop','exit_ts','exit_price','pnl']
    # getSymbolsFromToday()
    global stage
    stage = "STAGE- 10  "
    instruments = getSymbolsFromToday() #  ["NSE_EQ|INE118H01025","NSE_EQ|INE465A01025"] ####    ["NSE_FO|51498"] #     instruments_Nontrending +instruments_trending   ["NSE_FO|51502","NSE_EQ|INE01EA01019"] #
    for symbol in instruments :
        startDate = "2025-12-15"
        endDate="2025-12-16"
        simulateLiveTicksToRouter(symbol, startDate, endDate)

        # candles_1m =   fetch_upstox_intraday(symbol)## getUpstoxCandleDataAndNormalizeTS(symbol , startDate , endDate ,"minutes",1)

        # trades = getTradesFromToday(symbol=symbol)
      
        # if len(trades) > 0 :
        #     plotMe(symbol,candles_1m,trades)


        #  ###################################   
        # print(trades)




        # file_path = f'{symbol.replace("|","_")}_trades.csv'
        
        # with open(file_path, mode='a', newline='') as file:
        #     writer = csv.writer(file)
        #     writer.writerow(field_names)
        #     for trade in trades:
        #         writer.writerow([symbol ,trade.entry_ts, trade.entry_price ,trade.mae, trade.mfe, trade.exit_reason, trade.side , trade.stop,   trade.exit_ts ,trade.exit_price, trade.pnl])
       



# =========================
# METRICS
# =========================

 
def summarize(trades):
    global stage
    if not trades:
        print("No trades")
        return

    df = pd.DataFrame([{
        "side": t.side,
        "pnl": t.exit_price-t.entry_price if t.side=="LONG" else t.entry_price -t.exit_price
        # "mae": t.mae,
        # "mfe": t.mfe,
        # # "duration_ms": t.duration_ms
    } for t in trades]).dropna()

    print("\n===== STAGE: "+stage   +" =====")
    print(df.groupby("side")[["pnl"]].mean())

    # valid = df["mae"] != 0
    # if valid.any():
    #     ratio = df.loc[valid, "mfe"] / abs(df.loc[valid, "mae"])
    #     print("\nMFE / |MAE| Ratio:")
    #     print(ratio.describe())



       
main() 