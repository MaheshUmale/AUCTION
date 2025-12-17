import asyncio
from fastapi import FastAPI, WebSocket
from router import LiveMarketRouter
from replay import replay

app = FastAPI()
router = LiveMarketRouter()
clients = set()

class Broadcaster:
    async def broadcast_fp(self, symbol, data):
        for ws in clients:
            await ws.send_json({"type": "fp", "symbol": symbol, **data})

    async def broadcast_dom(self, symbol, data):
        for ws in clients:
            await ws.send_json({"type": "dom", "symbol": symbol, **data})

broadcaster = Broadcaster()

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("cmd") == "replay":
                await replay(msg["symbol"], ws)
    finally:
        clients.remove(ws)
