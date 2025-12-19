import sys
import os
import logging
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import zmq
import asyncio
import json
from typing import Set
import threading

# Add project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.insert(0, project_root)

import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount the 'frontend' directory to serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_root():
    with open("frontend/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

# In-memory store for connected clients
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
            # Keep the connection open
            await websocket.receive_text()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.remove(websocket)
        logger.info("WebSocket connection closed.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
