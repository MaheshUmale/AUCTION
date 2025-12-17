from symbol_engine import SymbolEngine

class LiveMarketRouter:
    def __init__(self):
        self.engines = {}

    def get_engine(self, symbol):
        if symbol not in self.engines:
            self.engines[symbol] = SymbolEngine(symbol)
        return self.engines[symbol]

    async def on_feed(self, symbol, snap, broadcaster):
        engine = self.get_engine(symbol)
        await engine.on_snapshot(snap, broadcaster)
