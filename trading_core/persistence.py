# persistence.py
import psycopg2
from questdb.ingress import Sender, TimestampNanos
from pymongo import MongoClient, ASCENDING
from typing import Dict, List
from trading_core.models import *
from dataclasses import asdict
import traceback
import sys
from datetime import datetime

class QuestDBPersistence:
    def __init__(self, host="localhost", ingest_port=9009, query_port=8812, db_name="auction_trading"):
        self.ingest_host = host
        self.ingest_port = ingest_port
        self.query_host = host
        self.query_port = query_port
        self.db_name = db_name
        self.conf = f'tcp::addr={self.ingest_host}:{self.ingest_port};'
        self._create_tables()

    def _get_conn(self):
        return psycopg2.connect(
            host=self.query_host,
            port=self.query_port,
            user="admin",
            password="quest",
            database=self.db_name,
        )

    def _create_tick_data_table(self, cur):
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tick_data (
            timestamp TIMESTAMP,
            instrument_key SYMBOL CAPACITY 512 CACHE,
            feed_type SYMBOL CAPACITY 256 CACHE,
            ltp DOUBLE,
            ltq LONG,
            cp DOUBLE,
            oi LONG,
            atp DOUBLE,
            vtt LONG,
            tbq DOUBLE,
            tsq DOUBLE,
            delta DOUBLE,
            theta DOUBLE,
            gamma DOUBLE,
            vega DOUBLE,
            rho DOUBLE,
            iv DOUBLE,
            bid_price_1 DOUBLE,
            bid_qty_1 LONG,
            ask_price_1 DOUBLE,
            ask_qty_1 LONG,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            insertion_time TIMESTAMP
        ) timestamp(timestamp) PARTITION BY DAY WAL
        WITH maxUncommittedRows=500000, o3MaxLag=600000000us;
        """)

    def _create_tables(self):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                self._create_tick_data_table(cur)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS levels (
                    symbol SYMBOL,
                    price DOUBLE,
                    side SYMBOL,
                    created_ts TIMESTAMP,
                    last_used_ts TIMESTAMP
                ) timestamp(created_ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS open_trades (
                    symbol SYMBOL,
                    side SYMBOL,
                    entry_price DOUBLE,
                    entry_ts TIMESTAMP,
                    stop_price DOUBLE,
                    tp_price DOUBLE,
                    status SYMBOL
                ) timestamp(entry_ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS closed_trades (
                    symbol SYMBOL,
                    side SYMBOL,
                    entry_price DOUBLE,
                    entry_ts TIMESTAMP,
                    stop_price DOUBLE,
                    tp_price DOUBLE,
                    exit_price DOUBLE,
                    exit_ts TIMESTAMP,
                    reason SYMBOL,
                    pnl DOUBLE,
                    status SYMBOL
                ) timestamp(exit_ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS symbol_state (
                    symbol SYMBOL,
                    last_candle_ts TIMESTAMP
                ) timestamp(last_candle_ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS context_candles_15m (
                    symbol SYMBOL,
                    ts TIMESTAMP,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE
                ) timestamp(ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    symbol SYMBOL,
                    ts TIMESTAMP,
                    ltp DOUBLE,
                    volume LONG,
                    total_buy_qty LONG,
                    total_sell_qty LONG
                ) timestamp(ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS footprints (
                    symbol SYMBOL,
                    ts TIMESTAMP,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    levels STRING
                ) timestamp(ts);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS context_candles_60m (
                    symbol SYMBOL,
                    ts TIMESTAMP,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE
                ) timestamp(ts);
                """)

    def upsert_level(self, level: StructureLevel):
        with Sender.from_conf(self.conf) as sender:
            sender.row(
                'levels',
                symbols={
                    'symbol': level.symbol,
                    'side': level.side,
                },
                columns={
                    'price': level.price,
                    'last_used_ts': level.last_used_ts,
                },
                at=int(level.created_ts.timestamp() * 1000000)
            )

    def load_levels(self, symbol: str) -> List[Dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM levels WHERE symbol = %s LATEST ON created_ts PARTITION BY symbol", (symbol,))
                rows = cur.fetchall()
                # Convert list of tuples to list of dicts
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def load_levels_forAll(self) -> List[Dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM levels LATEST ON created_ts PARTITION BY symbol")
                rows = cur.fetchall()
                # Convert list of tuples to list of dicts
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def save_open_trade(self, tradeObj: Trade):
        with Sender.from_conf(self.conf) as sender:
            sender.row(
                'open_trades',
                symbols={
                    'symbol': tradeObj.symbol,
                    'side': tradeObj.side,
                    'status': tradeObj.status,
                },
                columns={
                    'entry_price': tradeObj.entry_price,
                    'stop_price': tradeObj.stop_price,
                    'tp_price': tradeObj.tp_price,
                },
                at=int(tradeObj.entry_ts.timestamp() * 1000000)
            )

    def close_trade(self, symbol: str, exit_price: float, exit_ts: int, reason: str, pnl:float):
        trade = self.get_open_trade(symbol)
        if trade:
            with Sender(self.ingest_host, self.ingest_port) as sender:
                sender.row(
                    'closed_trades',
                    symbols={
                        'symbol': trade['symbol'],
                        'side': trade['side'],
                        'reason': reason,
                        'status': 'CLOSED',
                    },
                    columns={
                        'entry_price': trade['entry_price'],
                        'stop_price': trade['stop_price'],
                        'tp_price': trade['tp_price'],
                        'exit_price': exit_price,
                        'pnl': pnl,
                    },
                    at=exit_ts
                )
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM open_trades WHERE symbol = %s", (symbol,))

    def load_open_trades(self) -> List[Dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM open_trades")
                rows = cur.fetchall()
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def load_closed_trades(self) -> List[Dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM closed_trades")
                rows = cur.fetchall()
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def get_open_trade(self, symbol) :
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM open_trades WHERE symbol = %s LATEST ON entry_ts PARTITION BY symbol", (symbol,))
                row = cur.fetchone()
                if row:
                    return dict(zip([column[0] for column in cur.description], row))
                return None

    def get_last_candle_ts(self, symbol: str) -> int | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT last_candle_ts FROM symbol_state WHERE symbol = %s LATEST ON last_candle_ts PARTITION BY symbol", (symbol,))
                row = cur.fetchone()
                if row:
                    return row[0]
                return None

    def save_context_candles(self, symbol: str, candles: List[Dict], timeframe_minutes: int) -> int:
        table_name = f"context_candles_{timeframe_minutes}m"
        with Sender(self.ingest_host, self.ingest_port) as sender:
            for candle in candles:
                sender.row(
                    table_name,
                    symbols={'symbol': symbol},
                    columns={
                        'open': candle['open'],
                        'high': candle['high'],
                        'low': candle['low'],
                        'close': candle['close'],
                        'volume': candle['volume'],
                    },
                    at=int(candle['ts'].timestamp() * 1000000)
                )
        return len(candles)

    def load_context_candles(self, symbol: str, timeframe_minutes: int, limit: int) -> List[Dict]:
        table_name = f"context_candles_{timeframe_minutes}m"
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table_name} WHERE symbol = %s ORDER BY ts DESC LIMIT %s", (symbol, limit))
                rows = cur.fetchall()
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def update_last_candle_ts(self, symbol: str, ts: int):
        with Sender(self.ingest_host, self.ingest_port) as sender:
            sender.row(
                'symbol_state',
                symbols={'symbol': symbol},
                at=ts
            )

    def save_footprint(self, symbol: str, footprint: Dict):
        with Sender(self.ingest_host, self.ingest_port) as sender:
            sender.row(
                'footprints',
                symbols={'symbol': symbol},
                columns={
                    'open': footprint['open'],
                    'high': footprint['high'],
                    'low': footprint['low'],
                    'close': footprint['close'],
                    'volume': footprint['volume'],
                    'levels': json.dumps(footprint['levels']),
                },
                at=int(footprint['ts'].timestamp() * 1000000)
            )

    def fetch_tick_data(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Fetches tick data for a given symbol and date range.
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                query = """
                SELECT timestamp as ts, instrument_key as symbol, ltp, vtt as volume, tbq as total_buy_qty, tsq as total_sell_qty
                FROM tick_data
                WHERE instrument_key = %s
                AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp;
                """
                cur.execute(query, (symbol, from_date, to_date))
                rows = cur.fetchall()
                return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def save_tick_data(self, data: Dict):
        with Sender.from_conf(self.conf) as sender:

            insertion_time = data.get('insertion_time')
            if isinstance(insertion_time, datetime):
                insertion_time = int(insertion_time.timestamp() * 1_000_000)

            sender.row(
                'tick_data',
                symbols={
                    'instrument_key': data['instrument_key'],
                    'feed_type': data['feed_type'],
                },
                columns={
                    'ltp': data.get('ltp'),
                    'ltq': data.get('ltq'),
                    'cp': data.get('cp'),
                    'oi': data.get('oi'),
                    'atp': data.get('atp'),
                    'vtt': data.get('vtt'),
                    'tbq': data.get('tbq'),
                    'tsq': data.get('tsq'),
                    'delta': data.get('delta'),
                    'theta': data.get('theta'),
                    'gamma': data.get('gamma'),
                    'vega': data.get('vega'),
                    'rho': data.get('rho'),
                    'iv': data.get('iv'),
                    'bid_price_1': data.get('bid_price_1'),
                    'bid_qty_1': data.get('bid_qty_1'),
                    'ask_price_1': data.get('ask_price_1'),
                    'ask_qty_1': data.get('ask_qty_1'),
                    'open': data.get('open'),
                    'high': data.get('high'),
                    'low': data.get('low'),
                    'close': data.get('close'),
                    'insertion_time': insertion_time
                },
                at=TimestampNanos(data['timestamp'] * 1000000)
            )
