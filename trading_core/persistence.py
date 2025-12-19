# trading_core/duckdb_persistence.py
import duckdb
import threading
from typing import Dict, List
import pandas as pd
from datetime import datetime
import json
from trading_core.models import StructureLevel, Trade
import config

class DuckDBPersistence:
    _instance = None
    _lock = threading.Lock()
    _thread_local = threading.local()

    def __new__(cls, *args, **kwargs):
        db_path = kwargs.get('db_path', config.DUCKDB_PATH)
        if not hasattr(cls, '_instances'):
            cls._instances = {}
        if db_path not in cls._instances:
            with cls._lock:
                if db_path not in cls._instances:
                    cls._instances[db_path] = super(DuckDBPersistence, cls).__new__(cls)
        return cls._instances[db_path]

    def __init__(self, db_path=config.DUCKDB_PATH):
        if hasattr(self, '_initialized') and self._initialized and self.db_path == db_path:
            return

        self.db_path = db_path
        # Create tables using the main thread's connection
        self._create_tables(self._get_conn())
        self._initialized = True
        self.tick_buffer = []
        self.buffer_lock = threading.Lock()
        self.buffer_limit = 1000

    def _get_conn(self):
        # Each thread gets its own connection
        if not hasattr(self._thread_local, 'conn') or self._thread_local.conn.isclosed():
            self._thread_local.conn = duckdb.connect(database=self.db_path, read_only=False)
        return self._thread_local.conn

    def _create_tables(self, conn):
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS tick_data (
                timestamp TIMESTAMP, instrument_key VARCHAR, feed_type VARCHAR, ltp DOUBLE, ltt BIGINT, ltq BIGINT, cp DOUBLE, oi BIGINT, atp DOUBLE, vtt BIGINT, tbq DOUBLE, tsq DOUBLE, delta DOUBLE, theta DOUBLE, gamma DOUBLE, vega DOUBLE, rho DOUBLE, iv DOUBLE, bid_price_1 DOUBLE, bid_qty_1 BIGINT, ask_price_1 DOUBLE, ask_qty_1 BIGINT, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, insertion_time TIMESTAMP, processed_time TIMESTAMP
            );""")
            cur.execute("CREATE TABLE IF NOT EXISTS levels (symbol VARCHAR, price DOUBLE, side VARCHAR, created_ts TIMESTAMP, last_used_ts TIMESTAMP);")
            cur.execute("CREATE TABLE IF NOT EXISTS open_trades (symbol VARCHAR, side VARCHAR, entry_price DOUBLE, entry_ts TIMESTAMP, stop_price DOUBLE, tp_price DOUBLE, status VARCHAR);")
            cur.execute("CREATE TABLE IF NOT EXISTS closed_trades (symbol VARCHAR, side VARCHAR, entry_price DOUBLE, entry_ts TIMESTAMP, stop_price DOUBLE, tp_price DOUBLE, exit_price DOUBLE, exit_ts TIMESTAMP, reason VARCHAR, pnl DOUBLE, status VARCHAR);")
            cur.execute("CREATE TABLE IF NOT EXISTS symbol_state (symbol VARCHAR, last_candle_ts TIMESTAMP);")
            cur.execute("CREATE TABLE IF NOT EXISTS context_candles_15m (symbol VARCHAR, ts TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE);")
            cur.execute("CREATE TABLE IF NOT EXISTS context_candles_60m (symbol VARCHAR, ts TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE);")
            cur.execute("CREATE TABLE IF NOT EXISTS signals (strategy_id VARCHAR, symbol VARCHAR, side VARCHAR, price DOUBLE, timestamp TIMESTAMP);")
            cur.execute("CREATE TABLE IF NOT EXISTS paper_trades (strategy_id VARCHAR, symbol VARCHAR, side VARCHAR, entry_price DOUBLE, exit_price DOUBLE, entry_ts TIMESTAMP, exit_ts TIMESTAMP, pnl DOUBLE, status VARCHAR);")
            cur.execute("CREATE TABLE IF NOT EXISTS ticks (symbol VARCHAR, ts TIMESTAMP, ltp DOUBLE, volume BIGINT, total_buy_qty BIGINT, total_sell_qty BIGINT);")
            cur.execute("CREATE TABLE IF NOT EXISTS footprints (symbol VARCHAR, ts TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, levels VARCHAR);")

    def upsert_level(self, level: StructureLevel):
        self._get_conn().execute("INSERT INTO levels VALUES (?, ?, ?, ?, ?)", (level.symbol, level.side, level.price, level.last_used_ts, level.created_ts))

    def load_levels(self, symbol: str) -> List[Dict]:
        return self._get_conn().execute("SELECT * FROM levels WHERE symbol = ?", (symbol,)).fetchdf().to_dict('records')

    def load_levels_forAll(self) -> List[Dict]:
        return self._get_conn().execute("SELECT * FROM levels").fetchdf().to_dict('records')

    def save_open_trade(self, tradeObj: Trade):
        self._get_conn().execute("INSERT INTO open_trades VALUES (?, ?, ?, ?, ?, ?, ?)", (tradeObj.symbol, tradeObj.side, tradeObj.entry_price, tradeObj.entry_ts, tradeObj.stop_price, tradeObj.tp_price, tradeObj.status))

    def close_trade(self, symbol: str, exit_price: float, exit_ts: int, reason: str, pnl: float):
        trade = self.get_open_trade(symbol)
        if trade:
            conn = self._get_conn()
            conn.execute("INSERT INTO closed_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (trade['symbol'], trade['side'], trade['entry_price'], trade['entry_ts'], trade['stop_price'], trade['tp_price'], exit_price, exit_ts, reason, pnl, 'CLOSED'))
            conn.execute("DELETE FROM open_trades WHERE symbol = ?", (symbol,))

    def load_open_trades(self) -> List[Dict]:
        return self._get_conn().execute("SELECT * FROM open_trades").fetchdf().to_dict('records')

    def load_closed_trades(self) -> List[Dict]:
        return self._get_conn().execute("SELECT * FROM closed_trades").fetchdf().to_dict('records')

    def get_open_trade(self, symbol) -> Dict:
        result = self._get_conn().execute("SELECT * FROM open_trades WHERE symbol = ? ORDER BY entry_ts DESC LIMIT 1", (symbol,)).fetchdf()
        return result.to_dict('records')[0] if not result.empty else None

    def get_last_candle_ts(self, symbol: str) -> int | None:
        result = self._get_conn().execute("SELECT last_candle_ts FROM symbol_state WHERE symbol = ? ORDER BY last_candle_ts DESC LIMIT 1", (symbol,)).fetchone()
        return result[0] if result else None

    def save_context_candles(self, symbol: str, candles: List[Dict], timeframe_minutes: int):
        if not candles: return 0
        table_name = f"context_candles_{timeframe_minutes}m"
        df = pd.DataFrame(candles)
        df['symbol'] = symbol
        conn = self._get_conn()
        conn.register('candles_df', df)
        conn.execute(f"INSERT INTO {table_name} SELECT symbol, ts, open, high, low, close, volume FROM candles_df")
        return len(candles)

    def load_context_candles(self, symbol: str, timeframe_minutes: int, limit: int) -> List[Dict]:
        table_name = f"context_candles_{timeframe_minutes}m"
        return self._get_conn().execute(f"SELECT * FROM {table_name} WHERE symbol = ? ORDER BY ts DESC LIMIT ?", (symbol, limit)).fetchdf().to_dict('records')

    def update_last_candle_ts(self, symbol: str, ts: int):
        self._get_conn().execute("INSERT INTO symbol_state (symbol, last_candle_ts) VALUES (?, ?)", (symbol, ts))

    def save_footprint(self, symbol: str, footprint: Dict):
        self._get_conn().execute("INSERT INTO footprints VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (symbol, footprint['ts'], footprint['open'], footprint['high'], footprint['low'], footprint['close'], footprint['volume'], json.dumps(footprint['levels'])))

    def fetch_tick_data(self, symbol: str, from_date: str, to_date: str) -> pd.DataFrame:
        query = "SELECT timestamp as ts, instrument_key as symbol, ltp, vtt as volume, tbq as total_buy_qty, tsq as total_sell_qty FROM tick_data WHERE instrument_key = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp;"
        return self._get_conn().execute(query, (symbol, from_date, to_date)).fetchdf()

    def save_market_data(self, data: Dict):
        with self.buffer_lock:
            self.tick_buffer.append(data)
            if len(self.tick_buffer) >= self.buffer_limit:
                self.flush_tick_buffer()

    def save_market_data_batch(self, data: List[Dict]):
        if not data: return
        with self.buffer_lock:
            self.tick_buffer.extend(data)
            if len(self.tick_buffer) >= self.buffer_limit:
                self.flush_tick_buffer()

    def flush_tick_buffer(self):
        with self.buffer_lock:
            if not self.tick_buffer: return
            df = pd.DataFrame(self.tick_buffer)
            df = df.reindex(columns=['timestamp', 'instrument_key', 'feed_type', 'ltp', 'ltt', 'ltq', 'cp', 'oi', 'atp', 'vtt', 'tbq', 'tsq', 'delta', 'theta', 'gamma', 'vega', 'rho', 'iv', 'bid_price_1', 'bid_qty_1', 'ask_price_1', 'ask_qty_1', 'open', 'high', 'low', 'close', 'insertion_time', 'processed_time'], fill_value=None)
            conn = self._get_conn()
            conn.register('tick_buffer', df)
            conn.execute('INSERT INTO tick_data SELECT * FROM tick_buffer')
            self.tick_buffer.clear()

    def get_all_symbols(self) -> List[str]:
        result = self._get_conn().execute("SELECT DISTINCT instrument_key FROM tick_data;").fetchall()
        return [row[0] for row in result]

    def get_recent_candles(self, symbol: str, limit: int) -> List[Dict]:
        query = "SELECT timestamp as ts, open, high, low, close, vtt as volume FROM tick_data WHERE instrument_key = ? AND feed_type = 'CANDLE_I1' ORDER BY timestamp DESC LIMIT ?;"
        return self._get_conn().execute(query, (symbol, limit)).fetchdf().to_dict('records')

    def close_thread_connection(self):
        """Closes the connection for the calling thread."""
        if hasattr(self._thread_local, 'conn'):
            self._thread_local.conn.close()
            del self._thread_local.conn

    def shutdown(self):
        """Performs a final flush and closes the calling thread's connection."""
        self.flush_tick_buffer()
        self.close_thread_connection()
