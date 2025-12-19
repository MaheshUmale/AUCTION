import sys
import os
import logging
from fastapi import FastAPI, WebSocket, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import zmq
import asyncio
import json
from typing import Set, List
import threading
import psycopg2
import pandas as pd
import plotly.graph_objects as go

# Add project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.insert(0, project_root)

import config
from trading_core.persistence import QuestDBPersistence
from trading_core.models import Tick
from strategy.renko_aggregator import RenkoAggregator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount the 'frontend' directory to serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Setup templates
templates = Jinja2Templates(directory="api/templates")

# --- Mock Engine for Trade Viewer ---
class MockEngine:
    class MockTradeEngine:
        def get_open_trade_count(self):
            return 0
        def get_open_trades_list(self):
            return {}
        open_trades = {}
        closed_trades = []
    trade_engine = MockTradeEngine()

engine = MockEngine()

# --- WebSocket and ZMQ ---
connected_clients: Set[WebSocket] = set()

def zmq_listener():
    """Listens to the ZeroMQ bus and broadcasts messages to all connected WebSockets."""
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(config.ZMQ_PUB_URL)
    sub_socket.setsockopt(zmq.SUBSCRIBE, config.ZMQ_TOPIC.encode('utf-8'))
    logger.info("ZMQ listener started and connected.")

    try:
        while True:
            topic, message = sub_socket.recv_multipart()
            data = json.loads(message.decode('utf-8'))
            logger.info(f"Received from ZMQ: {data}")
            # Broadcast to all connected clients
            for client in connected_clients:
                asyncio.run(client.send_json(data))
    except Exception as e:
        logger.error(f"Error in ZMQ listener: {e}")
    finally:
        sub_socket.close()

@app.on_event("startup")
async def startup_event():
    threading.Thread(target=zmq_listener, daemon=True).start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted.")
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.remove(websocket)
        logger.info("WebSocket connection closed.")

# --- Main Page ---
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- Query UI ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.environ.get("QUESTDB_HOST", "localhost"),
            port=os.environ.get("QUESTDB_PORT", 8812),
            user=os.environ.get("QUESTDB_USER", "admin"),
            password=os.environ.get("QUESTDB_PASSWORD", "quest"),
            database=os.environ.get("QUESTDB_DB", "auction_trading")
        )
        return conn
    except psycopg2.OperationalError as e:
        raise Exception(f"Could not connect to QuestDB: {e}")

@app.get("/query")
async def query_get(request: Request):
    return templates.TemplateResponse("query_ui.html", {"request": request, "query": "SELECT * FROM trades LIMIT 10;", "results": None, "error": None})

@app.post("/query")
async def query_post(request: Request, query: str = Form(...)):
    results_html = None
    error = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:
                column_names = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                df = pd.DataFrame(results, columns=column_names)
                results_html = df.to_html(classes='table table-striped dataframe', index=False)
            else:
                results_html = "<p>Query executed successfully, no results to display.</p>"
        conn.close()
    except Exception as e:
        error = str(e)
    return templates.TemplateResponse("query_ui.html", {"request": request, "query": query, "results": results_html, "error": error})

# --- Renko Chart ---
@app.get("/renko")
async def renko_get(request: Request):
    persistence = QuestDBPersistence()
    all_symbols = persistence.get_all_symbols()
    return templates.TemplateResponse("renko_chart.html", {"request": request, "all_symbols": all_symbols, "symbol": all_symbols[0] if all_symbols else "", "from_date": "2024-01-01", "to_date": "2024-01-02", "chart_html": None})

@app.post("/renko")
async def renko_post(request: Request, symbol: str = Form(...), from_date: str = Form(...), to_date: str = Form(...)):
    persistence = QuestDBPersistence()
    all_symbols = persistence.get_all_symbols()

    bricks = []
    def on_renko_brick(brick):
        bricks.append(brick)

    renko_aggregator = RenkoAggregator(on_renko_brick=on_renko_brick)

    tick_data = persistence.fetch_tick_data(symbol, from_date, to_date)
    for data in tick_data:
        try:
            tick = Tick(symbol=data['symbol'], ltp=data['ltp'], ts=data['ts'])
            renko_aggregator.on_tick(tick)
        except KeyError as e:
            logger.error(f"KeyError: {e} in tick data: {data}")

    chart_html = None
    if bricks:
        df = pd.DataFrame([brick.__dict__ for brick in bricks])
        fig = go.Figure(go.Candlestick(x=df['ts'], open=df['open'], high=df['high'], low=df['low'], close=df['close']))
        chart_html = fig.to_html(full_html=False)

    return templates.TemplateResponse("renko_chart.html", {"request": request, "all_symbols": all_symbols, "symbol": symbol, "from_date": from_date, "to_date": to_date, "chart_html": chart_html})

# --- Trade Viewer ---
@app.get("/trades")
async def trades_get(request: Request):
    # NOTE: Using mock engine data. In a real application, this data would
    # be fetched from a persistent store or a live data feed.
    open_trades = engine.trade_engine.open_trades
    closed_trades = engine.trade_engine.closed_trades
    return templates.TemplateResponse("trade_viewer.html", {"request": request, "open_trades": open_trades, "closed_trades": closed_trades})

@app.post("/renko-update")
async def update_renko(request: Request, brick_mode: str = Form(...), brick_value: float = Form(...)):
    logger.info(f"Received Renko update: mode={brick_mode}, value={brick_value}")
    # In a real application, this would update the live trading engine.
    # For now, we just log the values and redirect back to the trades page.
    return RedirectResponse(url="/trades", status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
