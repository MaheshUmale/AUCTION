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

import sys
import os

# Get the absolute path of the directory containing the script
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..") # Adjust ".." based on your structure

# Add the project root to the system path, inserting it at the beginning
sys.path.insert(0, project_root)





from google.protobuf.json_format import MessageToDict
import MarketDataFeedV3_pb2 as pb

from trading_core.stage8_engine import LiveAuctionEngine, LiveMarketRouter, Monitor
from ui import trade_viewer

import config
ACCESS_TOKEN = config.ACCESS_TOKEN

NiftyFO = ["NSE_FO|41910","NSE_FO|41913","NSE_FO|41914","NSE_FO|41915","NSE_FO|41916","NSE_FO|41917","NSE_FO|41918","NSE_FO|41921","NSE_FO|41922","NSE_FO|41923","NSE_FO|41924","NSE_FO|41925","NSE_FO|41926","NSE_FO|41927","NSE_FO|41928","NSE_FO|41935","NSE_FO|41936","NSE_FO|41939","NSE_FO|41940","NSE_FO|41943","NSE_FO|41944","NSE_FO|41945","NSE_FO|41946"]
BN_FO =["NSE_FO|51414","NSE_FO|51415","NSE_FO|51416","NSE_FO|51417","NSE_FO|51420","NSE_FO|51421","NSE_FO|51439","NSE_FO|51440","NSE_FO|51460","NSE_FO|51461","NSE_FO|51475","NSE_FO|51476","NSE_FO|51493","NSE_FO|51498","NSE_FO|51499","NSE_FO|51500","NSE_FO|51501","NSE_FO|51502","NSE_FO|51507","NSE_FO|51510","NSE_FO|60166","NSE_FO|60167"]


# append all 3 arrays into one
all_instruments = config.WATCHLIST + NiftyFO + BN_FO
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
    import traceback
    traceback.print_exc()

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
            INTERVAL_SECONDS = 2
            MAX_RETRIES = 10

            streamer.auto_reconnect(ENABLE_AUTO_RECONNECT, INTERVAL_SECONDS, MAX_RETRIES)

            # 4. Connect (Blocking Call)
            # --- Periodic Subscription (Keep-Alive) ---
            def subscription_keep_alive(streamer_ref, instruments):
                while True:
                    time.sleep(50) # Every 1 minute
                    try:
                        print(f"Sending periodic subscription for {len(instruments)} instruments...{datetime.now()}")
                        streamer_ref.subscribe(instruments, "full")
                    except Exception as e:
                        print(f"Periodic subscription failed: {e}")

            # Start keep-alive thread
            ka_thread = threading.Thread(target=subscription_keep_alive, args=(streamer, instrument_keys), daemon=True)
            ka_thread.start()

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
    start_websocket_thread(access_token=ACCESS_TOKEN,instrument_keys=config.WATCHLIST)
    threading.Thread(target=start_ui, daemon=True).start()
    # threading.Thread(target=start_wss, daemon=True).start()

    print("[SYSTEM] Live trading system started")

    # Keep main thread alive, with graceful shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt, shutting down...")
    finally:
        router.shutdown()

        print("System shut down.")
