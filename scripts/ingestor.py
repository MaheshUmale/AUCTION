import zmq
import threading
import json
import time
import sys
import os
import logging
from collections import deque

import config
from trading_core.persistence import QuestDBPersistence
from upstox_client import ApiClient, MarketDataStreamerV3, Configuration
from data_handling.feed_processor import save_feed_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WebSocket Publisher Thread ---

def on_message_handler(data, zmq_socket):
    """Callback to handle incoming WebSocket messages and publish them."""
    try:
        zmq_socket.send_multipart([config.ZMQ_TOPIC.encode('utf-8'), json.dumps(data).encode('utf-8')])
    except Exception as e:
        logger.error(f"Error publishing to ZeroMQ: {e}")

def start_websocket_publisher(access_token, instrument_keys, zmq_pub_url):
    """Starts the Upstox WebSocket client and publishes data to a ZeroMQ socket."""
    logger.info("Starting WebSocket publisher...")
    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind(zmq_pub_url)

    def run_streamer():
        configuration = Configuration()
        configuration.access_token = access_token
        api_client = ApiClient(configuration)

        streamer = MarketDataStreamerV3(api_client, instrument_keys, "full")
        streamer.on("message", lambda data: on_message_handler(data, pub_socket))
        streamer.on("open", lambda: logger.info("WebSocket Connected (Publisher)!"))
        streamer.on("error", lambda error: logger.error(f"WebSocket Error (Publisher): {error}"))
        streamer.on("close", lambda code, reason: logger.info(f"WebSocket Closed (Publisher): {code} - {reason}"))

        streamer.auto_reconnect(True, 5, 10)

        logger.info(f"Connecting to Upstox with {len(instrument_keys)} instruments...")
        streamer.connect()

    t = threading.Thread(target=run_streamer, daemon=True)
    t.start()
    logger.info("WebSocket publisher thread started.")

# --- QuestDB Writer Thread ---

def start_questdb_writer(zmq_sub_url):
    """
    Subscribes to the ZeroMQ feed, buffers messages in a deque, and writes
    them to QuestDB in batches.
    """
    logger.info("Starting QuestDB writer with batching...")

    message_queue = deque()
    lock = threading.Lock()
    BATCH_SIZE = 100
    FLUSH_INTERVAL = 5  # seconds

    def zmq_listener_thread():
        """Listens to ZMQ and adds messages to the thread-safe deque."""
        context = zmq.Context()
        sub_socket = context.socket(zmq.SUB)
        sub_socket.connect(zmq_sub_url)
        sub_socket.setsockopt(zmq.SUBSCRIBE, config.ZMQ_TOPIC.encode('utf-8'))
        while True:
            try:
                topic, message = sub_socket.recv_multipart()
                data = json.loads(message.decode('utf-8'))
                with lock:
                    message_queue.append(data)
            except Exception as e:
                logger.error(f"Error in ZMQ listener thread: {e}")

    def db_persister_thread():
        """Persists messages from the deque to QuestDB in batches."""
        persistence = QuestDBPersistence()
        while True:
            batch_to_persist = []
            with lock:
                while len(message_queue) > 0 and len(batch_to_persist) < BATCH_SIZE:
                    batch_to_persist.append(message_queue.popleft())

            if batch_to_persist:
                try:
                    for msg_data in batch_to_persist:
                        feeds = msg_data.get("feeds", {})
                        for symbol, feed in feeds.items():
                            save_feed_data(persistence, symbol, feed)
                    logger.info(f"Persisted batch of {len(batch_to_persist)} messages.")
                except Exception as e:
                    logger.error(f"Error persisting batch to QuestDB: {e}")

            # Sleep to prevent busy-waiting
            time.sleep(FLUSH_INTERVAL if not batch_to_persist else 0.1)

    # Start the listener and persister threads
    listener = threading.Thread(target=zmq_listener_thread, daemon=True)
    persister = threading.Thread(target=db_persister_thread, daemon=True)
    listener.start()
    persister.start()
    logger.info("QuestDB writer threads (listener and persister) started.")


# --- Main ---

if __name__ == "__main__":
    logger.info("Starting data ingestion service...")

    start_websocket_publisher(
        access_token=config.ACCESS_TOKEN,
        instrument_keys=config.WATCHLIST,
        zmq_pub_url=config.ZMQ_PUB_URL
    )

    start_questdb_writer(
        zmq_sub_url=config.ZMQ_PUB_URL
    )

    logger.info("Ingestion service is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down ingestion service.")
