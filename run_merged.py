import sys
import os
import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from typing import List
from datetime import datetime

# Ensure AUCTION module can be imported
sys.path.append(os.path.join(os.getcwd(), "AUCTION"))

# Import from AUCTION/main_live
# We use the globals defined there to ensure consistency
from AUCTION.main_live import engine, start_websocket_thread, ACCESS_TOKEN, initial_instruments, NiftyFO, BN_FO

# Define the merged application
app = FastAPI()

# WebSocket Logic
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass # Connection likely dead

manager = ConnectionManager()

# Broadcaster Hook for the Engine
def engine_broadcast_hook(symbol, data):
    # This runs in the Thread of the WSS, so we must be careful with AsyncIO
    # Broadcasting needs to happen on the main event loop or be thread-safe.
    # Uvicorn runs in an asyncio loop.
    # Calls from engine are in a separate thread (Upstox Streamer Thread).
    # We need to schedule the broadcast coroutine in the main loop.
    
    try:
        msg = json.dumps(data)
        # Verify loop exists
        try:
             loop = asyncio.get_running_loop()
        except RuntimeError:
             loop = None
        
        # If we are in the main thread loop context (unlikely for WSS callback), await it
        # But here we are likely in a background thread.
        # We need a reference to the main loop to run_coroutine_threadsafe.
        
        coro = manager.broadcast(msg)
        
        if MAIN_LOOP and loop != MAIN_LOOP:
             asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)
        elif loop:
             # We are in an event loop (maybe), create task
            loop.create_task(coro)
        else:
            coro.close()
            
    except RuntimeError as re:
        if "Event loop is closed" in str(re):
            # If loop closed, ensure coro is cleaned up
             try:
                 coro.close() 
             except: 
                 pass
        else:
            print(f"Broadcast Runtime Error: {re}")
            try: coro.close() 
            except: pass
    except Exception as e:
        print(f"Broadcast Error: {e}")
        try: coro.close() 
        except: pass

MAIN_LOOP = None

@app.on_event("startup")
async def startup_event():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    
    print(">>> STARTING MERGED APPLICATION <<<")
    
    # 1. Setup Broadcaster
    engine.set_broadcaster(engine_broadcast_hook)
    
    # 2. Start Upstox WSS (Background Thread)
    # Combine instruments
    all_instruments = initial_instruments + NiftyFO + BN_FO
    # Use a smaller subset for debug if needed? The user provided a token and list.
    # We use the full list.
    
    print(f"Starting WSS for {len(all_instruments)} instruments...")
    start_websocket_thread(ACCESS_TOKEN, all_instruments)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages from frontend if any (e.g. subscription requests)
            # Currently frontend just listens.
            pass
    except Exception:
        manager.disconnect(websocket)

# Serve Frontend
# We mount the 'frontend' directory to root / for static files (e.g. style.css, app.js)
# But we also need to serve index.html at root "/"
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def get():
    return HTMLResponse(open("frontend/index.html").read())

# Symbol List Endpoint (Frontend calls /symbols)
@app.get("/symbols")
async def get_symbols():
    # Return list of symbols being tracked
    # We can get keys from engine or the static list
    return initial_instruments + NiftyFO + BN_FO

# MongoDB for History
from motor.motor_asyncio import AsyncIOMotorClient
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["auction_trading"]
collection = db["footprints"]

# History Endpoint (Frontend calls /history/SYMBOL)
@app.get("/history/{symbol}")
async def get_history(symbol: str):
    # Fetch from MongoDB
    cursor = collection.find({"symbol": symbol}).sort("ts", 1)
    bars = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        bars.append(doc)
    return bars

# Trades Endpoint
@app.get("/trades", response_class=HTMLResponse)
async def view_trades():
    # Fetch Data
    open_trades = []
    if engine.trade_engine.open_trades:
        # It's a dict {symbol: Trade}
        open_trades = list(engine.trade_engine.open_trades.values())
        
    closed_trades = engine.trade_engine.closed_trades
    
    # Helper for Rows
    def make_rows(trades_list, is_open=False):
        rows = ""
        for t in trades_list:
            symbol = getattr(t, 'symbol', 'N/A')
            side = getattr(t, 'side', 'N/A')
            entry = getattr(t, 'entry_price', 0)
            
            pnl = getattr(t, 'pnl')
            now_price = getattr(t, 'exit_price')
            
            # Dynamic Calc for Open Trades
            if is_open:
                # Try to get live price from engine
                current_price = 0
                if symbol in engine.footprint_builders:
                     current_price = engine.footprint_builders[symbol].close
                
                now_price = current_price if current_price > 0 else "Waiting..."
                
                if current_price > 0:
                    multiplier = 1 if side == "LONG" or side == "BUY" else -1
                    pnl = (current_price - entry) * multiplier
                    pnl = round(pnl, 2)
                else:
                    pnl = "Calc..."
            else:
                 # Closed Trade
                 if now_price is None: now_price = "-"
            
            # Simple color for PnL
            row_class = ""
            if isinstance(pnl, (int, float)):
                if pnl > 0: row_class = "table-success"
                elif pnl < 0: row_class = "table-danger"
                
            # Format Time
            ts_raw = getattr(t, 'entry_ts', 0)
            ts_str = "-"
            if ts_raw:
                try:
                    ts_dt = datetime.fromtimestamp(ts_raw / 1000)
                    ts_str = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    ts_str = str(ts_raw)
            ts_raw_exit = getattr(t, 'exit_ts', 0)
            ts_str_exit = "-"
            if ts_raw_exit:
                try:
                    ts_dt = datetime.fromtimestamp(ts_raw_exit / 1000)
                    ts_str_exit = ts_dt.strftime('%H:%M:%S')
                except:
                    ts_str_exit = str(ts_raw_exit)

            rows += f"<tr class='{row_class}'><td><a href='/?symbol={symbol}' target='_blank' style='color: white; text-decoration: none;'>{symbol} ➚</a></td><td>{side}</td><td>{entry}</td><td>{now_price}</td><td>{pnl}</td><td>{ts_str}</td><td>{ts_str_exit}</td></tr>"
        return rows

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Trades</title>
        <meta http-equiv="refresh" content="2"> <!-- Auto Refresh every 2s -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style> body {{ padding: 20px; background: #111; color: #eee; }} .table {{ color: #eee; }} </style>
    </head>
    <body>
        <div class="container container-fluid">
            <h1>Live Trade Monitor</h1>
            <h3 class="mt-4">Open Trades ({len(open_trades)})</h3>
            <table class="table table-dark table-striped table-sm">
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>LTP</th><th>Unrealized PnL</th><th>Time</th></tr></thead>
                <tbody>
                    {make_rows(open_trades, is_open=True)}
                </tbody>
            </table>
            
            <h3 class="mt-4">Closed Trades ({len(closed_trades)})</h3>
             <table class="table table-dark table-striped table-sm">
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>Realized PnL</th><th>Entry Time</th><th>Exit Time</th></tr></thead>
                <tbody>
                    {make_rows(closed_trades, is_open=False)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return html

@app.get("/api/trades/{symbol}")
async def get_symbol_trades(symbol: str):
    trades = []
    # 1. Closed Trades
    for t in engine.trade_engine.closed_trades:
        if t.symbol == symbol:
            trades.append({
                "side": t.side,
                "entry_price": t.entry_price,
                "entry_ts": t.entry_ts,
                "exit_price": t.exit_price,
                "exit_ts": t.exit_ts,
                "pnl": t.pnl,
                "status": "CLOSED"
            })
            
    # 2. Open Trades
    for t in engine.trade_engine.open_trades.values():
        if t.symbol == symbol:
             trades.append({
                "side": t.side,
                "entry_price": t.entry_price,
                "entry_ts": t.entry_ts,
                "exit_price": None, # or current LTP?
                "exit_ts": None,
                "pnl": None,
                "status": "OPEN"
            })
    
    return trades

@app.get("/{filename}")
async def get_file(filename: str):
    # Fallback to serve files from frontend dir directly if not found in mount
    # This is useful for app.js, style.css linked as "app.js" not "/static/app.js"
    potential_path = os.path.join("frontend", filename)
    if os.path.exists(potential_path):
        return FileResponse(potential_path)
    return {"error": "File not found"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
