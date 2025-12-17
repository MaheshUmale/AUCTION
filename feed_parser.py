def extract_market_ff(msg, symbol):
    ff = msg["feeds"][symbol]["fullFeed"]["marketFF"]

    bidask = ff.get("marketLevel", {}).get("bidAskQuote", [])

    return {
        "ltp": float(ff.get("ltpc", {}).get("ltp", 0) or 0),
        "ltq": int(ff.get("ltpc", {}).get("ltq", 0) or 0),
        "bidask": bidask,
        "atp": float(ff.get("atp", 0) or 0),
        "tbq": int(ff.get("tbq", 0) or 0),
        "tsq": int(ff.get("tsq", 0) or 0),
    }
