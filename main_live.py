import asyncio
import threading
import ssl
import json
import requests
import websockets

import json
import websocket
import threading
import time
from datetime import datetime


from google.protobuf.json_format import MessageToDict
import MarketDataFeedV3_pb2 as pb

from stage8_engine import LiveAuctionEngine, LiveMarketRouter, Monitor
import trade_viewer

ACCESS_TOKEN = "YOUR_TOKEN_HERE"
ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTNmODdiZmFmYjg1ZjI4MWU4NGE4NTgiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NTc3MTE5OSwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY1ODM2MDAwfQ.swKHghB44IqQ5DgchNaCGHaG8W9cFVwcjmbHUsC7ynU'
initial_instruments =["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank","NSE_EQ|INE585B01010","NSE_EQ|INE139A01034","NSE_EQ|INE1NPP01017","NSE_EQ|INE917I01010","NSE_EQ|INE267A01025","NSE_EQ|INE466L01038","NSE_EQ|INE070A01015","NSE_EQ|INE749A01030","NSE_EQ|INE171Z01026","NSE_EQ|INE591G01025","NSE_EQ|INE160A01022","NSE_EQ|INE814H01029","NSE_EQ|INE102D01028","NSE_EQ|INE134E01011","NSE_EQ|INE009A01021","NSE_EQ|INE376G01013","NSE_EQ|INE619A01035","NSE_EQ|INE465A01025","NSE_EQ|INE540L01014","NSE_EQ|INE237A01028","NSE_EQ|INE361B01024","NSE_EQ|INE811K01011","NSE_EQ|INE01EA01019","NSE_EQ|INE030A01027","NSE_EQ|INE476A01022","NSE_EQ|INE721A01047","NSE_EQ|INE028A01039","NSE_EQ|INE670K01029","NSE_EQ|INE158A01026","NSE_EQ|INE123W01016","NSE_EQ|INE192A01025","NSE_EQ|INE118A01012","NSE_EQ|INE674K01013","NSE_EQ|INE094A01015","NSE_EQ|INE528G01035","NSE_EQ|INE093I01010","NSE_EQ|INE073K01018","NSE_EQ|INE006I01046","NSE_EQ|INE142M01025","NSE_EQ|INE169A01031","NSE_EQ|INE849A01020","NSE_EQ|INE669C01036","NSE_EQ|INE216A01030","NSE_EQ|INE111A01025","NSE_EQ|INE062A01020","NSE_EQ|INE081A01020","NSE_EQ|INE883A01011","NSE_EQ|INE075A01022","NSE_EQ|INE498L01015","NSE_EQ|INE377N01017","NSE_EQ|INE484J01027","NSE_EQ|INE205A01025","NSE_EQ|INE027H01010","NSE_EQ|INE121A01024","NSE_EQ|INE974X01010","NSE_EQ|INE854D01024","NSE_EQ|INE742F01042","NSE_EQ|INE226A01021","NSE_EQ|INE047A01021","NSE_EQ|INE326A01037","NSE_EQ|INE584A01023","NSE_EQ|INE414G01012","NSE_EQ|INE669E01016","NSE_EQ|INE211B01039","NSE_EQ|INE813H01021","NSE_EQ|INE213A01029","NSE_EQ|INE335Y01020","NSE_EQ|INE931S01010","NSE_EQ|INE704P01025","NSE_EQ|INE053F01010","NSE_EQ|INE127D01025","NSE_EQ|INE021A01026","NSE_EQ|INE356A01018","NSE_EQ|INE733E01010","NSE_EQ|INE115A01026","NSE_EQ|INE702C01027","NSE_EQ|INE388Y01029","NSE_EQ|INE117A01022","NSE_EQ|INE239A01024","NSE_EQ|INE437A01024","NSE_EQ|INE245A01021","NSE_EQ|INE053A01029","NSE_EQ|INE196A01026","NSE_EQ|INE121J01017","NSE_EQ|INE399L01023","NSE_EQ|INE121E01018","NSE_EQ|INE019A01038","NSE_EQ|INE151A01013","NSE_EQ|INE522F01014","NSE_EQ|INE296A01032","NSE_EQ|INE066F01020","NSE_EQ|INE002A01018","NSE_EQ|INE203G01027","NSE_EQ|INE467B01029","NSE_EQ|INE0ONG01011","NSE_EQ|INE079A01024","NSE_EQ|INE0J1Y01017","NSE_EQ|INE260B01028","NSE_EQ|INE040A01034","NSE_EQ|INE121A08PJ0","NSE_EQ|INE603J01030","NSE_EQ|INE202E01016","NSE_EQ|INE663F01032","NSE_EQ|INE066A01021","NSE_EQ|INE752E01010","NSE_EQ|INE271C01023","NSE_EQ|INE318A01026","NSE_EQ|INE918I01026","NSE_EQ|INE758E01017","NSE_EQ|INE089A01031","NSE_EQ|INE848E01016","NSE_EQ|INE982J01020","NSE_EQ|INE761H01022","NSE_EQ|INE494B01023","NSE_EQ|INE646L01027","NSE_EQ|INE0V6F01027","NSE_EQ|INE010B01027","NSE_EQ|INE302A01020","NSE_EQ|INE634S01028","NSE_EQ|INE397D01024","NSE_EQ|INE192R01011","NSE_EQ|INE775A08105","NSE_EQ|INE059A01026","NSE_EQ|INE377Y01014","NSE_EQ|INE343G01021","NSE_EQ|INE797F01020","NSE_EQ|INE180A01020","NSE_EQ|INE949L01017","NSE_EQ|INE881D01027","NSE_EQ|INE795G01014","NSE_EQ|INE280A01028","NSE_EQ|INE298A01020","NSE_EQ|INE155A01022","NSE_EQ|INE274J01014","NSE_EQ|INE012A01025","NSE_EQ|INE095A01012","NSE_EQ|INE562A01011","NSE_EQ|INE195A01028","NSE_EQ|INE118H01025","NSE_EQ|INE364U01010","NSE_EQ|INE238A01034","NSE_EQ|INE044A01036","NSE_EQ|INE379A01028","NSE_EQ|INE338I01027","NSE_EQ|INE935N01020","NSE_EQ|INE038A01020","NSE_EQ|INE031A01017","NSE_EQ|INE242A01010","NSE_EQ|INE692A01016","NSE_EQ|INE04I401011","NSE_EQ|INE061F01013","NSE_EQ|INE263A01024","NSE_EQ|INE020B01018","NSE_EQ|INE685A01028","NSE_EQ|INE647A01010","NSE_EQ|INE860A01027","NSE_EQ|INE0BS701011","NSE_EQ|INE00H001014","NSE_EQ|INE171A01029","NSE_EQ|INE262H01021","NSE_EQ|INE084A01016","NSE_EQ|INE775A01035","NSE_EQ|INE878B01027","NSE_EQ|INE018E01016","NSE_EQ|INE776C01039","NSE_EQ|INE417T01026","NSE_EQ|INE415G01027","NSE_EQ|INE821I01022","NSE_EQ|INE323A01026","NSE_EQ|INE214T01019","NSE_EQ|INE176B01034","NSE_EQ|INE249Z01020","NSE_EQ|INE343H01029","NSE_EQ|INE758T01015","NSE_EQ|INE154A01025","NSE_EQ|INE455K01017","NSE_EQ|INE406A01037","NSE_EQ|INE101A01026","NSE_EQ|INE208A01029","NSE_EQ|INE303R01014","NSE_EQ|INE090A01021","NSE_EQ|INE472A01039","NSE_EQ|INE628A01036","NSE_EQ|INE040H01021","NSE_EQ|INE018A01030","NSE_EQ|INE092T01019","NSE_EQ|INE067A01029","NSE_EQ|INE423A01024","NSE_EQ|INE259A01022","NSE_EQ|INE07Y701011","NSE_EQ|INE765G01017","NSE_EQ|INE257A01026","NSE_EQ|INE774D01024","NSE_EQ|INE129A01019","NSE_EQ|INE481G01011","NSE_EQ|INE114A01011","NSE_EQ|INE774D08MG3","NSE_EQ|INE935A01035","NSE_EQ|INE003A01024","NSE_EQ|INE029A01011","NSE_EQ|INE670A01012","NSE_EQ|INE200M01039","NSE_EQ|INE016A01026"]

NiftyFO = ["NSE_FO|41910","NSE_FO|41913","NSE_FO|41914","NSE_FO|41915","NSE_FO|41916","NSE_FO|41917","NSE_FO|41918","NSE_FO|41921","NSE_FO|41922","NSE_FO|41923","NSE_FO|41924","NSE_FO|41925","NSE_FO|41926","NSE_FO|41927","NSE_FO|41928","NSE_FO|41935","NSE_FO|41936","NSE_FO|41939","NSE_FO|41940","NSE_FO|41943","NSE_FO|41944","NSE_FO|41945","NSE_FO|41946"]
BN_FO =["NSE_FO|51414","NSE_FO|51415","NSE_FO|51416","NSE_FO|51417","NSE_FO|51420","NSE_FO|51421","NSE_FO|51439","NSE_FO|51440","NSE_FO|51460","NSE_FO|51461","NSE_FO|51475","NSE_FO|51476","NSE_FO|51493","NSE_FO|51498","NSE_FO|51499","NSE_FO|51500","NSE_FO|51501","NSE_FO|51502","NSE_FO|51507","NSE_FO|51510","NSE_FO|60166","NSE_FO|60167"]


# append all 3 arrays into one
all_instruments = initial_instruments + NiftyFO + BN_FO
# initial_test =["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank","NSE_EQ|INE585B01010"];
# all_instruments = initial_test
# ---------- Upstox Helpers ----------

def get_market_data_feed_authorize_v3():
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
    return requests.get(url, headers=headers).json()


def decode_protobuf(buffer):
    msg = pb.FeedResponse()
    msg.ParseFromString(buffer)
    return MessageToDict(msg)


# ---------- Core Objects ----------

engine = LiveAuctionEngine()
router = LiveMarketRouter(engine)
monitor = Monitor(engine)


from upstox_client.configuration import Configuration
from upstox_client import ApiClient,MarketDataStreamerV3,configuration,api_client

import upstox_client



def on_error(error):
    print(f"WebSocket Error: {error} {datetime.now()}")

def on_open():
    print(f"WebSocket Connected (SDK)! {datetime.now()}")

def on_close(code, reason):
    #print timestamp
    # print()
    print(f"WebSocket Closed: {code} - {reason} -{datetime.now()}")

def on_auto_reconnect_stopped(data):
    """Handler for when auto-reconnect retries are exhausted."""
    print(f" {datetime.now()} == Auto-reconnect stopped after retries: {data}")
    # Consider manual intervention or a higher-level retry here

def start_websocket_thread(access_token, instrument_keys):
    """Starts the Upstox SDK MarketDataStreamerV3 in a background thread."""
    
    def run_streamer():
        global streamer
        
        # Populate initial set 
        
        print(f"Starting UPSTOX SDK Streamer with {len(instrument_keys)} instruments...")
        
        # 1. Configure
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        
        # 2. Initialize Streamer
        # Note: The SDK manages the connection, auth, and auto-reconnects.
        try:
            print("DEBUG: Initializing ApiClient...", flush=True)
            api_client = upstox_client.ApiClient(configuration)
            print("DEBUG: ApiClient Initialized. Initializing Streamer...", flush=True)
            streamer = MarketDataStreamerV3(api_client, instrument_keys, "full")
            print("DEBUG: Streamer Initialized.", flush=True)
            
            # 3. Register Callbacks
            streamer.on("message", router.on_message)
            streamer.on("open", on_open)
            streamer.on("error", on_error)
            streamer.on("close", on_close)
            
            streamer.on("autoReconnectStopped", on_auto_reconnect_stopped)
            
            # --- Configure Auto-Reconnect ---
            # Enable auto-reconnect, set interval to 15 seconds, and max retries to 5
            ENABLE_AUTO_RECONNECT = True
            INTERVAL_SECONDS = 10
            MAX_RETRIES = 5

            streamer.auto_reconnect(ENABLE_AUTO_RECONNECT, INTERVAL_SECONDS, MAX_RETRIES)

            # 4. Connect (Blocking Call)
            print("Connecting to Upstox V3 via SDK...")
            streamer.connect()
            
        except Exception as e:
            print(f"SDK Streamer Fatal Error: {e}")
            import traceback
            traceback.print_exc()

    # Run in a daemon thread so it doesn't block the main app
    t = threading.Thread(target=run_streamer, daemon=True)
    t.start()
    return t
# ---------- WebSocket Loop ----------

async def fetch_market_data():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    auth = get_market_data_feed_authorize_v3()
    uri = auth["data"]["authorized_redirect_uri"]

    async with websockets.connect(uri, ssl=ssl_context) as ws:
        print("[WSS] Connected")

        sub = {
            "guid": "auction-engine",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys":  all_instruments
            }
        }

        await ws.send(json.dumps(sub).encode("utf-8"))

        while True:
            raw = await ws.recv()
            data = decode_protobuf(raw)
            router.on_message(data)
            await asyncio.sleep(0)



# ---------- Thread Wrappers ----------

def start_wss():
    asyncio.run(fetch_market_data())


def start_ui():
    trade_viewer.start(engine)


# ---------- Boot ----------

if __name__ == "__main__":

    monitor.start()  # non-blocking internal loop
    start_websocket_thread(access_token=ACCESS_TOKEN,instrument_keys=initial_instruments)
    threading.Thread(target=start_ui, daemon=True).start()
    # threading.Thread(target=start_wss, daemon=True).start()

    print("[SYSTEM] Live trading system started")

    # Keep main thread alive
    while True:
        pass
