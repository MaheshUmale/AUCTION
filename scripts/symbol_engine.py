from inference import OrderFlowInferer
from footprint import FootprintBuilder
from dom import DOMBook
from mongo import store_footprint, store_dom
from config import FOOTPRINT_TF_SEC, TICK_SIZE

class SymbolEngine:
    def __init__(self, symbol):
        self.symbol = symbol
        self.infer = OrderFlowInferer(TICK_SIZE)
        self.fp = FootprintBuilder(FOOTPRINT_TF_SEC)
        self.dom = DOMBook()
        self.last_ts = 0

    async def on_snapshot(self, snap, broadcaster):
        flow = self.infer.infer(snap)
        self.fp.on_flow(flow)
        self.dom.update(snap["bidask"])

        now = snap["ts"]
        if now - self.fp.start_ts >= FOOTPRINT_TF_SEC:
            fp_snap = self.fp.snapshot(snap["atp"])
            await store_footprint(self.symbol, fp_snap)
            await broadcaster.broadcast_fp(self.symbol, fp_snap)
            self.fp.reset()

        dom_snap = self.dom.snapshot()
        await store_dom(self.symbol, dom_snap)
        await broadcaster.broadcast_dom(self.symbol, dom_snap)
