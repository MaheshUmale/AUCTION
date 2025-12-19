class DOMBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}

    def update(self, bidask):
        self.bids.clear()
        self.asks.clear()
        for l in bidask:
            self.bids[l["bidP"]] = int(l["bidQ"])
            self.asks[l["askP"]] = int(l["askQ"])

    def snapshot(self):
        return {
            "bids": self.bids,
            "asks": self.asks
        }

