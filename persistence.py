# persistence.py
from pymongo import MongoClient, ASCENDING
from typing import Dict, List
from models import *
from dataclasses import asdict
import traceback
import sys

class MongoPersistence:
    def __init__(self, uri="mongodb://localhost:27017", db_name="auction_trading"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        self.levels = self.db.levels
        self.open_trades = self.db.open_trades
        self.closed_trades = self.db.closed_trades
        self.symbol_state = self.db.symbol_state

        self._ensure_indexes()

    def _ensure_indexes(self):
        self.levels.create_index(
            [("symbol", ASCENDING), ("price", ASCENDING), ("side", ASCENDING)],
            unique=True
        )
        self.open_trades.create_index("symbol", unique=True)
        self.symbol_state.create_index("symbol", unique=True)

   
    def upsert_level(self, level: StructureLevel):
        doc = asdict(level)

        self.levels.update_one(
            {
                "symbol": doc["symbol"],
                "price": doc["price"],
                "side": doc["side"]
            },
            {"$set": doc},
            upsert=True
        )


    def load_levels(self, symbol: str) -> List[Dict]:
        
        return list(self.levels.find({"symbol": symbol, "active": True})) 
    
    def load_levels_forAll(self):
        return list(self.levels.find({}, {"_id": 0}))
    
    # ---------- TRADES ----------
    def save_open_trade(self, tradeObj: Trade):
        trade = asdict(tradeObj)
        self.open_trades.replace_one(
            {"symbol": trade["symbol"]},
            trade,
            upsert=True
        )

    def close_trade(self, symbol: str, exit_price: float, exit_ts: int, reason: str, pnl:float):
        trade = self.open_trades.find_one_and_delete({"symbol": symbol})
        if trade:
            trade.update({
                "exit_price": exit_price,
                "exit_ts": exit_ts,
                "reason": reason,
                "status": "CLOSED",
                "pnl":pnl
            })
            self.closed_trades.insert_one(trade) 

    def load_open_trades(self):
        return list(self.open_trades.find({}, {"_id": 0}))

    def load_closed_trades(self):
        return list(self.closed_trades.find({}, {"_id": 0}))
    def get_open_trade(self, symbol) :
        trade = self.open_trades.find_one({"symbol": symbol}, {"_id": 0})
        return trade

    # ---------- SYMBOL STATE ----------
    def get_last_candle_ts(self, symbol: str) -> int | None:
        doc = self.symbol_state.find_one({"symbol": symbol},{"_id": 0})
        return doc["last_candle_ts"] if doc else None

    def update_last_candle_ts(self, symbol: str, ts: int):
        self.symbol_state.update_one(
            {"symbol": symbol},
            {"$set": {"last_candle_ts": ts}},
            upsert=True
        )

    def _strip_id(self, doc: dict) -> dict:
        doc.pop("_id", None)
        return doc
