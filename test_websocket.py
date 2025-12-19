import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket.")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"Received data: {data}")
            except websockets.ConnectionClosed:
                print("Connection closed.")
                break

if __name__ == "__main__":
    asyncio.run(test_websocket())
