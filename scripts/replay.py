from mongo import fp_col

async def replay(symbol, ws):
    cursor = fp_col.find({"symbol": symbol}).sort("ts", 1)
    async for doc in cursor:
        await ws.send_json({
            "type": "footprint",
            "symbol": symbol,
            **doc
        })

