import time
from feed_parser import extract_market_ff
from router import LiveMarketRouter
from server import broadcaster   # reuse same broadcaster

router = LiveMarketRouter()

async def on_broker_message(msg: dict):
    """
    Call this from your broker WSS on_message
    """
    current_ts = int(msg.get("currentTs", time.time()*1000)) // 1000

    feeds = msg.get("feeds", {})
    for symbol, data in feeds.items():
        ff = data.get("fullFeed", {}).get("marketFF")
        if not ff:
            continue

        snap = extract_market_ff(msg, symbol)
        snap["ts"] = current_ts

        await router.on_feed(symbol, snap, broadcaster)
