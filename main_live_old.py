import asyncio
import threading
import time
import json
from datetime import datetime
from collections import defaultdict

import upstox_client
from upstox_client import MarketDataStreamerV3
from motor.motor_asyncio import AsyncIOMotorClient

# ================= CONFIG =================

ACCESS_TOKEN = "YOUR_TOKEN_HERE"

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "market_fp"

FOOTPRINT_TF_SEC = 60
TICK_SIZE = 0.05

# ================= INSTRUMENTS =================

initial_instruments = [
    "NSE_INDEX|Nifty 50",
    "NSE_EQ|INE467B01029",
    "NSE_EQ|INE020B01018",
]

# ================= MONGO =================

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]
fp_col = db.footprints
dom_col = db.dom

# ================= CORE ENGINES =================

class OrderFlowInferer:
    def __init__(self):
        self.prev_tbq = 0
        self.prev_tsq = 0

    def infer(self, snap):
        book = snap["bidask"]
        if not book or snap["ltq"] == 0:
            return None

        best_bid = book[0]["bidP"]
        best_ask = book[0]["askP"]

        bid = ask = 0
        if snap["ltp"] >= best_ask:
            ask = snap["ltq"]
        elif snap["ltp"] <= best_bid:
            bid = snap["ltq"]
        else:
            bid = ask = snap["ltq"] // 2

        d_tbq = snap["tbq"] - self.prev_tbq
        d_tsq = snap["tsq"] - self.prev_tsq

        self.prev_tbq = snap["tbq"]
        self.prev_tsq = snap["tsq"]

        return {
            "price": round(snap["ltp"] / TICK_SIZE) * TICK_SIZE,
            "bid": bid,
            "ask": ask,
            "abs": d_tbq - d_tsq
        }


class FootprintBuilder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.start_ts = int(time.time() // FOOTPRINT_TF_SEC * FOOTPRINT_TF_SEC)
        self.levels = defaultdict(lambda: {"bid": 0, "ask": 0, "abs": 0})

    def on_flow(self, f):
        if not f:
            return
        lvl = self.levels[f["price"]]
        lvl["bid"] += f["bid"]
        lvl["ask"] += f["ask"]
        lvl["abs"] += f["abs"]

    def snapshot(self, symbol, atp):
        return {
            "symbol": symbol,
            "ts": self.start_ts,
            "levels": dict(self.levels),
            "delta": sum(v["ask"] - v["bid"] for v in self.levels.values()),
            "vwap": atp,
            "created_at": datetime.utcnow()
        }


class DOMBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}

    def update(self, bidask):
        self.bids.clear()
        self.asks.clear()
        for l in bidask:
            self.bids[l["bidP"]] = int(l["bidQ"])
            self.asks[l["askP"]] = int(l["askQ"])

    def snapshot(self, symbol):
        return {
            "symbol": symbol,
            "bids": self.bids,
            "asks": self.asks,
            "ts": int(time.time()),
        }


class SymbolEngine:
    def __init__(self, symbol):
        self.symbol = symbol
        self.infer = OrderFlowInferer()
        self.fp = FootprintBuilder()
        self.dom = DOMBook()

    async def on_snapshot(self, snap):
        flow = self.infer.infer(snap)
        self.fp.on_flow(flow)
        self.dom.update(snap["bidask"])

        now = int(time.time())
        if now - self.fp.start_ts >= FOOTPRINT_TF_SEC:
            fp_doc = self.fp.snapshot(self.symbol, snap["atp"])
            await fp_col.insert_one(fp_doc)
            self.fp.reset()

        await dom_col.insert_one(self.dom.snapshot(self.symbol))


# ================= ROUTER =================

class LiveMarketRouter:
    def __init__(self):
        self.engines = {}

    def get_engine(self, symbol):
        if symbol not in self.engines:
            self.engines[symbol] = SymbolEngine(symbol)
        return self.engines[symbol]

    def on_message(self, msg):
        """
        SDK CALLBACK (SYNC)
        """
        asyncio.run_coroutine_threadsafe(
            self._handle(msg),
            asyncio.get_event_loop()
        )

    async def _handle(self, msg):
        feeds = msg.get("feeds", {})
        ts = int(msg.get("currentTs", time.time()*1000)) // 1000

        for symbol, data in feeds.items():
            ff = data.get("fullFeed", {}).get("marketFF")
            if not ff:
                continue

            snap = {
                "ltp": float(ff.get("ltpc", {}).get("ltp", 0) or 0),
                "ltq": int(ff.get("ltpc", {}).get("ltq", 0) or 0),
                "bidask": ff.get("marketLevel", {}).get("bidAskQuote", []),
                "atp": float(ff.get("atp", 0) or 0),
                "tbq": int(ff.get("tbq", 0) or 0),
                "tsq": int(ff.get("tsq", 0) or 0),
                "ts": ts
            }

            engine = self.get_engine(symbol)
            await engine.on_snapshot(snap)

# ================= START STREAM =================

router = LiveMarketRouter()

def start_stream():
    config = upstox_client.Configuration()
    config.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(config)

    streamer = MarketDataStreamerV3(
        api_client,
        initial_instruments,
        "full"
    )

    streamer.on("message", router.on_message)
    streamer.on("open", lambda: print("[WSS] Connected"))
    streamer.on("close", lambda c, r: print("[WSS] Closed", c, r))
    streamer.on("error", lambda e: print("[WSS] Error", e))

    streamer.auto_reconnect(True, 10, 5)
    streamer.connect()

# ================= BOOT =================

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    t = threading.Thread(target=start_stream, daemon=True)
    t.start()

    print("[SYSTEM] Footprint + DOM engine running")

    loop.run_forever()
