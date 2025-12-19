import sys
import os
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import zmq
import asyncio
import json

# Add project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.insert(0, project_root)

import config

app = FastAPI()

# Mount the 'frontend' directory to serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_root():
    with open("frontend/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

# In-memory store for connected clients
connected_clients = set()

async def zmq_listener(websocket: WebSocket):
    """Listens to the ZeroMQ bus and forwards messages to the WebSocket."""
    context = zmq.asyncio.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(config.ZMQ_PUB_URL)
    sub_socket.setsockopt(zmq.SUBSCRIBE, config.ZMQ_TOPIC.encode('utf-8'))

    try:
        while True:
            topic, message = await sub_socket.recv_multipart()
            data = json.loads(message.decode('utf-8'))
            await websocket.send_json(data)
    except asyncio.CancelledError:
        pass
    finally:
        sub_socket.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    listener_task = asyncio.create_task(zmq_listener(websocket))
    try:
        while True:
            # Keep the connection open
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        listener_task.cancel()
        connected_clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
