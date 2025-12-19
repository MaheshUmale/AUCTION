import zmq
import threading
import json
import time
import sys
import os


import config
from trading_core.persistence import QuestDBPersistence
from upstox_client import ApiClient, MarketDataStreamerV3, Configuration
from data_handling.feed_processor import save_feed_data

# --- WebSocket Publisher Thread ---

def on_message_handler(data, zmq_socket):
    """Callback to handle incoming WebSocket messages and publish them."""
    try:
        zmq_socket.send_multipart([config.ZMQ_TOPIC.encode('utf-8'), json.dumps(data).encode('utf-8')])
    except Exception as e:
        print(f"Error publishing to ZeroMQ: {e}")

def start_websocket_publisher(access_token, instrument_keys, zmq_pub_url):
    """Starts the Upstox WebSocket client and publishes data to a ZeroMQ socket."""
    print("Starting WebSocket publisher...")
    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind(zmq_pub_url)

    def run_streamer():
        configuration = Configuration()
        configuration.access_token = access_token
        api_client = ApiClient(configuration)

        streamer = MarketDataStreamerV3(api_client, instrument_keys, "full")
        streamer.on("message", lambda data: on_message_handler(data, pub_socket))
        streamer.on("open", lambda: print("WebSocket Connected (Publisher)!"))
        streamer.on("error", lambda error: print(f"WebSocket Error (Publisher): {error}"))
        streamer.on("close", lambda code, reason: print(f"WebSocket Closed (Publisher): {code} - {reason}"))

        streamer.auto_reconnect(True, 5, 10)

        print(f"Connecting to Upstox with {len(instrument_keys)} instruments...")
        streamer.connect()

    t = threading.Thread(target=run_streamer, daemon=True)
    t.start()
    print("WebSocket publisher thread started.")

# --- QuestDB Writer Thread ---

def start_questdb_writer(zmq_sub_url):
    """Subscribes to the ZeroMQ feed and writes data to QuestDB."""
    print("Starting QuestDB writer...")
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(zmq_sub_url)
    sub_socket.setsockopt(zmq.SUBSCRIBE, b'market_data')

    persistence = QuestDBPersistence()

    def run_writer():
        while True:
            try:
                topic, message = sub_socket.recv_multipart()
                data = json.loads(message.decode('utf-8'))

                feeds = data.get("feeds", {})
                for symbol, feed in feeds.items():
                    save_feed_data(persistence, symbol, feed)
                    print(f"Persisted data for {symbol}")

            except Exception as e:
                print(f"Error in QuestDB writer: {e}")

    t = threading.Thread(target=run_writer, daemon=True)
    t.start()
    print("QuestDB writer thread started.")


# --- Main ---

if __name__ == "__main__":
    print("Starting data ingestion service...")

    start_websocket_publisher(
        access_token=config.ACCESS_TOKEN,
        instrument_keys=config.WATCHLIST,
        zmq_pub_url=config.ZMQ_PUB_URL
    )

    start_questdb_writer(
        zmq_sub_url=config.ZMQ_PUB_URL
    )

    print("Ingestion service is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down ingestion service.")
