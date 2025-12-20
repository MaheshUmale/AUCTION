# scripts/stress_test_duckdb.py
import sys
import os
import threading
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading_core.persistence import DuckDBPersistence

# --- Configuration ---
DB_PATH = "stress_test_trading_data.duckdb"
TEST_DURATION_SECONDS = 30
NUM_READER_THREADS = 5
WRITER_BATCH_SIZE = 100
WRITER_SLEEP_S = 0.1  # Sleep time for the writer thread

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Global State ---
stop_event = threading.Event()
error_occurred = threading.Event()
test_failed = False

def generate_mock_tick(instrument_key):
    """Generates a single mock tick data dictionary."""
    now = datetime.now()
    return {
        'timestamp': now, 'instrument_key': instrument_key, 'feed_type': 'TICK_DATA',
        'ltp': round(random.uniform(100.0, 500.0), 2), 'ltt': int(now.timestamp() * 1000),
        'ltq': random.randint(1, 1000), 'vtt': random.randint(1000, 100000),
        'atp': round(random.uniform(100.0, 500.0), 2), 'open': round(random.uniform(100.0, 500.0), 2),
        'high': round(random.uniform(100.0, 500.0), 2), 'low': round(random.uniform(100.0, 500.0), 2),
        'close': round(random.uniform(100.0, 500.0), 2), 'insertion_time': now, 'processed_time': now,
    }

def writer_thread(db_path: str, symbols: List[str]):
    """Continuously generates and saves mock market data in batches."""
    logging.info("Writer thread started.")
    persistence = None
    try:
        persistence = DuckDBPersistence(db_path=db_path)
        while not stop_event.is_set():
            batch = [generate_mock_tick(random.choice(symbols)) for _ in range(WRITER_BATCH_SIZE)]
            persistence.save_market_data_batch(batch)
            logging.info(f"Added {len(batch)} records to the buffer.")
            time.sleep(WRITER_SLEEP_S)
    except Exception as e:
        logging.error(f"Writer thread encountered an error: {e}", exc_info=True)
        error_occurred.set()
    finally:
        if persistence:
            persistence.close_thread_connection()
        logging.info("Writer thread finished.")

def reader_thread(db_path: str, symbols: List[str]):
    """Continuously runs various read queries against the database."""
    logging.info("Reader thread started.")
    persistence = None
    try:
        persistence = DuckDBPersistence(db_path=db_path)
        while not stop_event.is_set():
            all_symbols = persistence.get_all_symbols()
            if all_symbols:
                logging.debug(f"Read {len(all_symbols)} distinct symbols.")
            if symbols:
                symbol = random.choice(symbols)
                to_date = datetime.now()
                from_date = to_date - timedelta(seconds=10)
                df = persistence.fetch_tick_data(symbol, from_date.isoformat(), to_date.isoformat())
                if not df.empty:
                    logging.debug(f"Fetched {len(df)} rows for symbol {symbol}.")
            time.sleep(random.uniform(0.1, 0.5))
    except Exception as e:
        if "database is locked" in str(e).lower():
            logging.critical(f"DATABASE IS LOCKED! Error: {e}")
            error_occurred.set()
        else:
            logging.error(f"Reader thread encountered an error: {e}", exc_info=True)
    finally:
        if persistence:
            persistence.close_thread_connection()
        logging.info("Reader thread finished.")


def main():
    """Main function to set up and run the stress test."""
    global test_failed

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        logging.info(f"Removed existing test database: {DB_PATH}")

    main_persistence = None
    try:
        main_persistence = DuckDBPersistence(db_path=DB_PATH)
        logging.info("DuckDB persistence layer initialized for the main thread.")
    except Exception as e:
        logging.error(f"Failed to initialize DuckDB: {e}")
        test_failed = True
        return

    symbols_to_test = ["NIFTY_FUT", "BANKNIFTY_FUT", "RELIANCE_EQ", "HDFCBANK_EQ"]
    threads = []

    writer = threading.Thread(target=writer_thread, args=(DB_PATH, symbols_to_test), name="Writer")
    threads.append(writer)
    writer.start()

    for i in range(NUM_READER_THREADS):
        reader = threading.Thread(target=reader_thread, args=(DB_PATH, symbols_to_test), name=f"Reader-{i+1}")
        threads.append(reader)
        reader.start()

    logging.info(f"Stress test running for {TEST_DURATION_SECONDS} seconds...")
    start_time = time.time()
    seconds_elapsed = 0
    while seconds_elapsed < TEST_DURATION_SECONDS:
        if error_occurred.is_set():
            logging.error("An error was detected. Stopping the test early.")
            test_failed = True
            break
        time.sleep(1)
        seconds_elapsed = int(time.time() - start_time)
        if seconds_elapsed % 5 == 0:
            logging.info(f"Test progress: {seconds_elapsed}/{TEST_DURATION_SECONDS} seconds...")

    logging.info("Stopping all threads...")
    stop_event.set()
    for thread in threads:
        thread.join()
    logging.info("All threads have been joined.")

    if not test_failed:
        logging.info("Final verification of written data...")
        total_rows = main_persistence._get_conn().execute("SELECT COUNT(*) FROM tick_data").fetchone()[0]
        logging.info(f"Total rows in tick_data table: {total_rows}")
        if total_rows > 0:
            logging.info("Verification successful: Data was written to the database.")
        else:
            logging.warning("Verification warning: No data was written to the database.")
            test_failed = True

    if main_persistence:
        main_persistence.shutdown()
        logging.info("Main persistence layer shut down.")

    if test_failed or error_occurred.is_set():
        logging.error("--- STRESS TEST FAILED ---")
    else:
        logging.info("--- STRESS TEST PASSED ---")

if __name__ == "__main__":
    main()
    if test_failed:
        sys.exit(1)
    else:
        sys.exit(0)
