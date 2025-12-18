class OrderFlowInferer:
    def __init__(self, tick_size):
        self.tick_size = tick_size
        self.prev_tbq = 0
        self.prev_tsq = 0

    def infer(self, snap):
        ltp, ltq = snap["ltp"], snap["ltq"]
        book = snap["bidask"]
        if not book or ltq == 0:
            return None

        best_bid = book[0]["bidP"]
        best_ask = book[0]["askP"]

        bid = ask = 0
        if ltp >= best_ask:
            ask = ltq
        elif ltp <= best_bid:
            bid = ltq
        else:
            bid = ask = ltq // 2

        d_tbq = snap["tbq"] - self.prev_tbq
        d_tsq = snap["tsq"] - self.prev_tsq
        self.prev_tbq, self.prev_tsq = snap["tbq"], snap["tsq"]

        return {
            "price": round(ltp / self.tick_size) * self.tick_size,
            "bid": bid,
            "ask": ask,
            "absorption": d_tbq - d_tsq
        }
