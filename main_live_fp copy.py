import asyncio
import threading
import time
from datetime import datetime , UTC
from collections import defaultdict
import os

from fastapi import FastAPI, WebSocket
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
import upstox_client
from upstox_client import MarketDataStreamerV3

import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI

import asyncio
import threading
import time
from datetime import datetime
from collections import defaultdict
import os
import json # <--- ADD THIS
from fastapi import FastAPI, WebSocket, WebSocketDisconnect # Import WebSocketDisconnect
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
import upstox_client
from upstox_client import MarketDataStreamerV3
# ================= CONFIG =================
ACCESS_TOKEN = "PUT_YOUR_ACCESS_TOKEN_HERE"
ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTQwYjZhYWIwMTU5MjMwZjUyNzc5YTYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NTg0ODc0NiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY1OTIyNDAwfQ.iClOpRDJFFX5UXsH5-8SOxFJzeKXB_S2jlLJyq6HmnI'

initial_instruments =["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank","NSE_EQ|INE585B01010","NSE_EQ|INE139A01034","NSE_EQ|INE1NPP01017","NSE_EQ|INE917I01010","NSE_EQ|INE267A01025","NSE_EQ|INE466L01038","NSE_EQ|INE070A01015","NSE_EQ|INE749A01030","NSE_EQ|INE171Z01026","NSE_EQ|INE591G01025","NSE_EQ|INE160A01022","NSE_EQ|INE814H01029","NSE_EQ|INE102D01028","NSE_EQ|INE134E01011","NSE_EQ|INE009A01021","NSE_EQ|INE376G01013","NSE_EQ|INE619A01035","NSE_EQ|INE465A01025","NSE_EQ|INE540L01014","NSE_EQ|INE237A01028","NSE_EQ|INE361B01024","NSE_EQ|INE811K01011","NSE_EQ|INE01EA01019","NSE_EQ|INE030A01027","NSE_EQ|INE476A01022","NSE_EQ|INE721A01047","NSE_EQ|INE028A01039","NSE_EQ|INE670K01029","NSE_EQ|INE158A01026","NSE_EQ|INE123W01016","NSE_EQ|INE192A01025","NSE_EQ|INE118A01012","NSE_EQ|INE674K01013","NSE_EQ|INE094A01015","NSE_EQ|INE528G01035","NSE_EQ|INE093I01010","NSE_EQ|INE073K01018","NSE_EQ|INE006I01046","NSE_EQ|INE142M01025","NSE_EQ|INE169A01031","NSE_EQ|INE849A01020","NSE_EQ|INE669C01036","NSE_EQ|INE216A01030","NSE_EQ|INE111A01025","NSE_EQ|INE062A01020","NSE_EQ|INE081A01020","NSE_EQ|INE883A01011","NSE_EQ|INE075A01022","NSE_EQ|INE498L01015","NSE_EQ|INE377N01017","NSE_EQ|INE484J01027","NSE_EQ|INE205A01025","NSE_EQ|INE027H01010","NSE_EQ|INE121A01024","NSE_EQ|INE974X01010","NSE_EQ|INE854D01024","NSE_EQ|INE742F01042","NSE_EQ|INE226A01021","NSE_EQ|INE047A01021","NSE_EQ|INE326A01037","NSE_EQ|INE584A01023","NSE_EQ|INE414G01012","NSE_EQ|INE669E01016","NSE_EQ|INE211B01039","NSE_EQ|INE813H01021","NSE_EQ|INE213A01029","NSE_EQ|INE335Y01020","NSE_EQ|INE931S01010","NSE_EQ|INE704P01025","NSE_EQ|INE053F01010","NSE_EQ|INE127D01025","NSE_EQ|INE021A01026","NSE_EQ|INE356A01018","NSE_EQ|INE733E01010","NSE_EQ|INE115A01026","NSE_EQ|INE702C01027","NSE_EQ|INE388Y01029","NSE_EQ|INE117A01022","NSE_EQ|INE239A01024","NSE_EQ|INE437A01024","NSE_EQ|INE245A01021","NSE_EQ|INE053A01029","NSE_EQ|INE196A01026","NSE_EQ|INE121J01017","NSE_EQ|INE399L01023","NSE_EQ|INE121E01018","NSE_EQ|INE019A01038","NSE_EQ|INE151A01013","NSE_EQ|INE522F01014","NSE_EQ|INE296A01032","NSE_EQ|INE066F01020","NSE_EQ|INE002A01018","NSE_EQ|INE203G01027","NSE_EQ|INE467B01029","NSE_EQ|INE0ONG01011","NSE_EQ|INE079A01024","NSE_EQ|INE0J1Y01017","NSE_EQ|INE260B01028","NSE_EQ|INE040A01034","NSE_EQ|INE121A08PJ0","NSE_EQ|INE603J01030","NSE_EQ|INE202E01016","NSE_EQ|INE663F01032","NSE_EQ|INE066A01021","NSE_EQ|INE752E01010","NSE_EQ|INE271C01023","NSE_EQ|INE318A01026","NSE_EQ|INE918I01026","NSE_EQ|INE758E01017","NSE_EQ|INE089A01031","NSE_EQ|INE848E01016","NSE_EQ|INE982J01020","NSE_EQ|INE761H01022","NSE_EQ|INE494B01023","NSE_EQ|INE646L01027","NSE_EQ|INE0V6F01027","NSE_EQ|INE010B01027","NSE_EQ|INE302A01020","NSE_EQ|INE634S01028","NSE_EQ|INE397D01024","NSE_EQ|INE192R01011","NSE_EQ|INE775A08105","NSE_EQ|INE059A01026","NSE_EQ|INE377Y01014","NSE_EQ|INE343G01021","NSE_EQ|INE797F01020","NSE_EQ|INE180A01020","NSE_EQ|INE949L01017","NSE_EQ|INE881D01027","NSE_EQ|INE795G01014","NSE_EQ|INE280A01028","NSE_EQ|INE298A01020","NSE_EQ|INE155A01022","NSE_EQ|INE274J01014","NSE_EQ|INE012A01025","NSE_EQ|INE095A01012","NSE_EQ|INE562A01011","NSE_EQ|INE195A01028","NSE_EQ|INE118H01025","NSE_EQ|INE364U01010","NSE_EQ|INE238A01034","NSE_EQ|INE044A01036","NSE_EQ|INE379A01028","NSE_EQ|INE338I01027","NSE_EQ|INE935N01020","NSE_EQ|INE038A01020","NSE_EQ|INE031A01017","NSE_EQ|INE242A01010","NSE_EQ|INE692A01016","NSE_EQ|INE04I401011","NSE_EQ|INE061F01013","NSE_EQ|INE263A01024","NSE_EQ|INE020B01018","NSE_EQ|INE685A01028","NSE_EQ|INE647A01010","NSE_EQ|INE860A01027","NSE_EQ|INE0BS701011","NSE_EQ|INE00H001014","NSE_EQ|INE171A01029","NSE_EQ|INE262H01021","NSE_EQ|INE084A01016","NSE_EQ|INE775A01035","NSE_EQ|INE878B01027","NSE_EQ|INE018E01016","NSE_EQ|INE776C01039","NSE_EQ|INE417T01026","NSE_EQ|INE415G01027","NSE_EQ|INE821I01022","NSE_EQ|INE323A01026","NSE_EQ|INE214T01019","NSE_EQ|INE176B01034","NSE_EQ|INE249Z01020","NSE_EQ|INE343H01029","NSE_EQ|INE758T01015","NSE_EQ|INE154A01025","NSE_EQ|INE455K01017","NSE_EQ|INE406A01037","NSE_EQ|INE101A01026","NSE_EQ|INE208A01029","NSE_EQ|INE303R01014","NSE_EQ|INE090A01021","NSE_EQ|INE472A01039","NSE_EQ|INE628A01036","NSE_EQ|INE040H01021","NSE_EQ|INE018A01030","NSE_EQ|INE092T01019","NSE_EQ|INE067A01029","NSE_EQ|INE423A01024","NSE_EQ|INE259A01022","NSE_EQ|INE07Y701011","NSE_EQ|INE765G01017","NSE_EQ|INE257A01026","NSE_EQ|INE774D01024","NSE_EQ|INE129A01019","NSE_EQ|INE481G01011","NSE_EQ|INE114A01011","NSE_EQ|INE774D08MG3","NSE_EQ|INE935A01035","NSE_EQ|INE003A01024","NSE_EQ|INE029A01011","NSE_EQ|INE670A01012","NSE_EQ|INE200M01039","NSE_EQ|INE016A01026"]

NiftyFO = ["NSE_FO|41910","NSE_FO|41913","NSE_FO|41914","NSE_FO|41915","NSE_FO|41916","NSE_FO|41917","NSE_FO|41918","NSE_FO|41921","NSE_FO|41922","NSE_FO|41923","NSE_FO|41924","NSE_FO|41925","NSE_FO|41926","NSE_FO|41927","NSE_FO|41928","NSE_FO|41935","NSE_FO|41936","NSE_FO|41939","NSE_FO|41940","NSE_FO|41943","NSE_FO|41944","NSE_FO|41945","NSE_FO|41946"]
BN_FO =["NSE_FO|51414","NSE_FO|51415","NSE_FO|51416","NSE_FO|51417","NSE_FO|51420","NSE_FO|51421","NSE_FO|51439","NSE_FO|51440","NSE_FO|51460","NSE_FO|51461","NSE_FO|51475","NSE_FO|51476","NSE_FO|51493","NSE_FO|51498","NSE_FO|51499","NSE_FO|51500","NSE_FO|51501","NSE_FO|51502","NSE_FO|51507","NSE_FO|51510","NSE_FO|60166","NSE_FO|60167"]


# append all 3 arrays into one
all_instruments = initial_instruments + NiftyFO + BN_FO
import asyncio
import threading
import time
from datetime import datetime
from collections import defaultdict
import os
import asyncio
import threading
import time
from datetime import datetime , UTC
from collections import defaultdict
import os

# --- Re-import for clean access
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse # <-- NEW IMPORT
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
import upstox_client
from upstox_client import MarketDataStreamerV3
from contextlib import asynccontextmanager


from fastapi import FastAPI, WebSocket
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
import upstox_client
from upstox_client import MarketDataStreamerV3

# ================= CONFIG =================
# ACCESS_TOKEN = "PUT_YOUR_ACCESS_TOKEN_HERE"
# ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTQwYjZhYWIwMTU5MjMwZjUyNzc5YTYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NTg0ODc0NiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY1OTIyNDAwfQ.iClOpRDJFFX5UXsH5-8SOxFJzeKXB_S2jlLJyq6HmnI' # NOTE: Reverted to placeholder as this is sensitive data

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "market_fp"
FOOTPRINT_TF_SEC = 60
TICK_SIZE = 0.05
WS_PORT = int(os.getenv("FP_PORT", "8000"))

INSTRUMENTS =  all_instruments
 
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "market_fp"
FOOTPRINT_TF_SEC = 60
TICK_SIZE = 0.05
WS_PORT = int(os.getenv("FP_PORT", "8000"))

# Combined Instruments (using your provided list)
initial_instruments =["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank","NSE_EQ|INE585B01010","NSE_EQ|INE139A01034","NSE_EQ|INE1NPP01017","NSE_EQ|INE917I01010","NSE_EQ|INE267A01025","NSE_EQ|INE466L01038","NSE_EQ|INE070A01015","NSE_EQ|INE749A01030","NSE_EQ|INE171Z01026","NSE_EQ|INE591G01025","NSE_EQ|INE160A01022","NSE_EQ|INE814H01029","NSE_EQ|INE102D01028","NSE_EQ|INE134E01011","NSE_EQ|INE009A01021","NSE_EQ|INE376G01013","NSE_EQ|INE619A01035","NSE_EQ|INE465A01025","NSE_EQ|INE540L01014","NSE_EQ|INE237A01028","NSE_EQ|INE361B01024","NSE_EQ|INE811K01011","NSE_EQ|INE01EA01019","NSE_EQ|INE030A01027","NSE_EQ|INE476A01022","NSE_EQ|INE721A01047","NSE_EQ|INE028A01039","NSE_EQ|INE670K01029","NSE_EQ|INE158A01026","NSE_EQ|INE123W01016","NSE_EQ|INE192A01025","NSE_EQ|INE118A01012","NSE_EQ|INE674K01013","NSE_EQ|INE094A01015","NSE_EQ|INE528G01035","NSE_EQ|INE093I01010","NSE_EQ|INE073K01018","NSE_EQ|INE006I01046","NSE_EQ|INE142M01025","NSE_EQ|INE169A01031","NSE_EQ|INE849A01020","NSE_EQ|INE669C01036","NSE_EQ|INE216A01030","NSE_EQ|INE111A01025","NSE_EQ|INE062A01020","NSE_EQ|INE081A01020","NSE_EQ|INE883A01011","NSE_EQ|INE075A01022","NSE_EQ|INE498L01015","NSE_EQ|INE377N01017","NSE_EQ|INE484J01027","NSE_EQ|INE205A01025","NSE_EQ|INE027H01010","NSE_EQ|INE121A01024","NSE_EQ|INE974X01010","NSE_EQ|INE854D01024","NSE_EQ|INE742F01042","NSE_EQ|INE226A01021","NSE_EQ|INE047A01021","NSE_EQ|INE326A01037","NSE_EQ|INE584A01023","NSE_EQ|INE414G01012","NSE_EQ|INE669E01016","NSE_EQ|INE211B01039","NSE_EQ|INE813H01021","NSE_EQ|INE213A01029","NSE_EQ|INE335Y01020","NSE_EQ|INE931S01010","NSE_EQ|INE704P01025","NSE_EQ|INE053F01010","NSE_EQ|INE127D01025","NSE_EQ|INE021A01026","NSE_EQ|INE356A01018","NSE_EQ|INE733E01010","NSE_EQ|INE115A01026","NSE_EQ|INE702C01027","NSE_EQ|INE388Y01029","NSE_EQ|INE117A01022","NSE_EQ|INE239A01024","NSE_EQ|INE437A01024","NSE_EQ|INE245A01021","NSE_EQ|INE053A01029","NSE_EQ|INE196A01026","NSE_EQ|INE121J01017","NSE_EQ|INE399L01023","NSE_EQ|INE121E01018","NSE_EQ|INE019A01038","NSE_EQ|INE151A01013","NSE_EQ|INE522F01014","NSE_EQ|INE296A01032","NSE_EQ|INE066F01020","NSE_EQ|INE002A01018","NSE_EQ|INE203G01027","NSE_EQ|INE467B01029","NSE_EQ|INE0ONG01011","NSE_EQ|INE079A01024","NSE_EQ|INE0J1Y01017","NSE_EQ|INE260B01028","NSE_EQ|INE040A01034","NSE_EQ|INE121A08PJ0","NSE_EQ|INE603J01030","NSE_EQ|INE202E01016","NSE_EQ|INE663F01032","NSE_EQ|INE066A01021","NSE_EQ|INE752E01010","NSE_EQ|INE271C01023","NSE_EQ|INE318A01026","NSE_EQ|INE918I01026","NSE_EQ|INE758E01017","NSE_EQ|INE089A01031","NSE_EQ|INE848E01016","NSE_EQ|INE982J01020","NSE_EQ|INE761H01022","NSE_EQ|INE494B01023","NSE_EQ|INE646L01027","NSE_EQ|INE0V6F01027","NSE_EQ|INE010B01027","NSE_EQ|INE302A01020","NSE_EQ|INE634S01028","NSE_EQ|INE397D01024","NSE_EQ|INE192R01011","NSE_EQ|INE775A08105","NSE_EQ|INE059A01026","NSE_EQ|INE377Y01014","NSE_EQ|INE343G01021","NSE_EQ|INE797F01020","NSE_EQ|INE180A01020","NSE_EQ|INE949L01017","NSE_EQ|INE881D01027","NSE_EQ|INE795G01014","NSE_EQ|INE280A01028","NSE_EQ|INE298A01020","NSE_EQ|INE155A01022","NSE_EQ|INE274J01014","NSE_EQ|INE012A01025","NSE_EQ|INE095A01012","NSE_EQ|INE562A01011","NSE_EQ|INE195A01028","NSE_EQ|INE118H01025","NSE_EQ|INE364U01010","NSE_EQ|INE238A01034","NSE_EQ|INE044A01036","NSE_EQ|INE379A01028","NSE_EQ|INE338I01027","NSE_EQ|INE935N01020","NSE_EQ|INE038A01020","NSE_EQ|INE031A01017","NSE_EQ|INE242A01010","NSE_EQ|INE692A01016","NSE_EQ|INE04I401011","NSE_EQ|INE061F01013","NSE_EQ|INE263A01024","NSE_EQ|INE020B01018","NSE_EQ|INE685A01028","NSE_EQ|INE647A01010","NSE_EQ|INE860A01027","NSE_EQ|INE0BS701011","NSE_EQ|INE00H001014","NSE_EQ|INE171A01029","NSE_EQ|INE262H01021","NSE_EQ|INE084A01016","NSE_EQ|INE775A01035","NSE_EQ|INE878B01027","NSE_EQ|INE018E01016","NSE_EQ|INE776C01039","NSE_EQ|INE417T01026","NSE_EQ|INE415G01027","NSE_EQ|INE821I01022","NSE_EQ|INE323A01026","NSE_EQ|INE214T01019","NSE_EQ|INE176B01034","NSE_EQ|INE249Z01020","NSE_EQ|INE343H01029","NSE_EQ|INE758T01015","NSE_EQ|INE154A01025","NSE_EQ|INE455K01017","NSE_EQ|INE406A01037","NSE_EQ|INE101A01026","NSE_EQ|INE208A01029","NSE_EQ|INE303R01014","NSE_EQ|INE090A01021","NSE_EQ|INE472A01039","NSE_EQ|INE628A01036","NSE_EQ|INE040H01021","NSE_EQ|INE018A01030","NSE_EQ|INE092T01019","NSE_EQ|INE067A01029","NSE_EQ|INE423A01024","NSE_EQ|INE259A01022","NSE_EQ|INE07Y701011","NSE_EQ|INE765G01017","NSE_EQ|INE257A01026","NSE_EQ|INE774D01024","NSE_EQ|INE129A01019","NSE_EQ|INE481G01011","NSE_EQ|INE114A01011","NSE_EQ|INE774D08MG3","NSE_EQ|INE935A01035","NSE_EQ|INE003A01024","NSE_EQ|INE029A01011","NSE_EQ|INE670A01012","NSE_EQ|INE200M01039","NSE_EQ|INE016A01026"]
NiftyFO = ["NSE_FO|41910","NSE_FO|41913","NSE_FO|41914","NSE_FO|41915","NSE_FO|41916","NSE_FO|41917","NSE_FO|41918","NSE_FO|41921","NSE_FO|41922","NSE_FO|41923","NSE_FO|41924","NSE_FO|41925","NSE_FO|41926","NSE_FO|41927","NSE_FO|41928","NSE_FO|41935","NSE_FO|41936","NSE_FO|41939","NSE_FO|41940","NSE_FO|41943","NSE_FO|41944","NSE_FO|41945","NSE_FO|41946"]
BN_FO =["NSE_FO|51414","NSE_FO|51415","NSE_FO|51416","NSE_FO|51417","NSE_FO|51420","NSE_FO|51421","NSE_FO|51439","NSE_FO|51440","NSE_FO|51460","NSE_FO|51461","NSE_FO|51475","NSE_FO|51476","NSE_FO|51493","NSE_FO|51498","NSE_FO|51499","NSE_FO|51500","NSE_FO|51501","NSE_FO|51502","NSE_FO|51507","NSE_FO|51510","NSE_FO|60166","NSE_FO|60167"]
INSTRUMENTS = initial_instruments + NiftyFO + BN_FO

# ================= MONGO =================
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]
fp_col = db.footprints
dom_col = db.dom

# ================= GLOBAL ASYNC LOOP =================
ASYNC_LOOP = None

# ================= CORE ENGINES (Unchanged) =================




# Import ObjectId from bson (usually available when motor is installed)
from bson import ObjectId 
# If 'from bson import ObjectId' fails, try 'from motor.motor_core import ObjectId'

# ================= CUSTOM SERIALIZER FUNCTION =================
def json_serializer(obj):
    """Custom JSON serializer for ObjectId and datetime objects."""
    if isinstance(obj, ObjectId):
        # Convert ObjectId to its string representation
        return str(obj)
    if isinstance(obj, datetime):
        # Convert datetime to ISO 8601 string format
        return obj.isoformat()
    
    # Let the default encoder handle other types or raise a TypeError
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
# ================= END CUSTOM SERIALIZER FUNCTION =================



# ... (OrderFlowInferer, FootprintBuilder, DOMBook, SymbolEngine are unchanged)
class OrderFlowInferer:
    # ... (Omitted for brevity)
    def __init__(self):
        self.prev_tbq = 0
        self.prev_tsq = 0

    def infer(self, snap):
        book = snap.get("bidask") or []
        if not book or snap.get("ltq", 0) == 0:
            return None
        best_bid = book[0]["bidP"]
        best_ask = book[0]["askP"]
        bid = ask = 0
        if snap["ltp"] >= best_ask:
            ask = snap["ltq"]
        elif snap["ltp"] <= best_bid:
            bid = snap["ltq"]
        else:
            bid = ask = snap["ltq"] // 2
        d_tbq = snap.get("tbq", 0) - self.prev_tbq
        d_tsq = snap.get("tsq", 0) - self.prev_tsq
        self.prev_tbq = snap.get("tbq", 0)
        self.prev_tsq = snap.get("tsq", 0)
        return {
            "price": round(snap["ltp"] / TICK_SIZE) * TICK_SIZE,
            "bid": bid,
            "ask": ask,
            "abs": d_tbq - d_tsq
        }

class FootprintBuilder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.start_ts = int(time.time() // FOOTPRINT_TF_SEC * FOOTPRINT_TF_SEC)
        self.levels = defaultdict(lambda: {"bid":0,"ask":0,"abs":0})

    def on_flow(self, f):
        if not f:
            return
        lvl = self.levels[f["price"]]
        lvl["bid"] += f["bid"]
        lvl["ask"] += f["ask"]
        lvl["abs"] += f["abs"]

    def snapshot(self, symbol, atp):
        return {
            "symbol": symbol,
            "ts": self.start_ts,
            "levels": dict(self.levels),
            "delta": sum(v["ask"]-v["bid"] for v in self.levels.values()),
            "vwap": atp,
            "created_at": datetime.now(UTC)
        }

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

    def snapshot(self, symbol):
        return {
            "symbol": symbol,
            "bids": self.bids,
            "asks": self.asks,
            "ts": int(time.time())
        }

class SymbolEngine:
    def __init__(self, symbol):
        self.symbol = symbol
        self.infer = OrderFlowInferer()
        self.fp = FootprintBuilder()
        self.dom = DOMBook()

    async def on_snapshot(self, snap):
        flow = self.infer.infer(snap)
        self.fp.on_flow(flow)
        self.dom.update(snap.get("bidask") or [])

        now = int(time.time())
        if now - self.fp.start_ts >= FOOTPRINT_TF_SEC:
            fp_doc = self.fp.snapshot(self.symbol, snap.get("atp",0))
            await fp_col.insert_one(fp_doc)
            await broadcast({"type":"footprint", **fp_doc})
            self.fp.reset()

        dom_doc = self.dom.snapshot(self.symbol)
        await dom_col.insert_one(dom_doc)
        await broadcast({"type":"dom", **dom_doc})

# ================= ROUTER (Unchanged) =================
class LiveMarketRouter:
    def __init__(self):
        self.engines = {}

    def get_engine(self, symbol):
        if symbol not in self.engines:
            self.engines[symbol] = SymbolEngine(symbol)
        return self.engines[symbol]

    def on_message(self, msg):
        if ASYNC_LOOP is None:
            print("[ERROR] ASYNC_LOOP not ready. Message dropped.")
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._handle(msg),
                ASYNC_LOOP
            )
        except Exception as e:
            print(f"[ERROR] Failed to submit _handle to ASYNC_LOOP: {repr(e)}")

    async def _handle(self, msg):
        # ... (Omitted for brevity)
        try:
            feeds = msg.get("feeds")
            if not feeds:
                return
            ts = int(msg.get("currentTs", time.time()*1000))
            for symbol, payload in feeds.items():
                full = payload.get("fullFeed", {})
                # ... (rest of parsing logic)
                ff = None
                ff_type = None
                if "marketFF" in full:
                    ff = full["marketFF"]
                    ff_type = "market"
                elif "indexFF" in full:
                    ff = full["indexFF"]
                    ff_type = "index"
                else:
                    continue
                ltpc = ff.get("ltpc", {})
                marketLevel = ff.get("marketLevel", {})
                bidAsk = marketLevel.get("bidAskQuote", [])
                ohlc = ff.get("marketOHLC", {}).get("ohlc", [])
                doc = {
                    "symbol": symbol,
                    "type": ff_type,
                    "ts": ts,
                    "ltp": ltpc.get("ltp"),
                    "ltt": ltpc.get("ltt"),
                    "cp": ltpc.get("cp"),
                    "bidAsk": bidAsk,
                    "ohlc": ohlc,
                    "atp": ff.get("atp"),
                    "tbq": ff.get("tbq"),
                    "tsq": ff.get("tsq")
                }
                if doc.get("ltp") is None or doc.get("atp") is None:
                    continue

                engine = self.get_engine(symbol)
                await engine.on_snapshot(doc)
                fp_col.insert_one(doc)
        except Exception as e:
            import traceback
            print("🔥 HANDLE ERROR 🔥", repr(e))
            traceback.print_exc()

# ================= FASTAPI WS/HTML =================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ASYNC_LOOP
    ASYNC_LOOP = asyncio.get_event_loop()
    print(f"[SYSTEM] ASYNC_LOOP successfully set to {ASYNC_LOOP} in FastAPI startup.")
    threading.Thread(target=start_upstox_stream, daemon=True).start()
    print(f"[SYSTEM] Upstox stream thread started.")
    yield
    print("[SYSTEM] Application shutting down.")

app = FastAPI(lifespan=lifespan)
clients = set() 

# --- FIX 1: Remove StaticFiles mount and replace with direct HTML serving. ---



# --- CRITICAL FIXES APPLIED IN JAVASCRIPT ---
html_content = """

<!DOCTYPE html>
<html>
<head>
  <title>Live Footprint Chart</title>
  <style>
    body { font-family: sans-serif; }
    canvas { background-color: #f7f7f7; }
    #container { display: flex; }
    #controls { margin-bottom: 10px; }
  </style>
</head>
<body>
  <h1>Footprint + DOM Ladder</h1> 
  <div id="controls">
    <label for="symbol-select">Select Instrument:</label>
    <select id="symbol-select">
      <option value="NSE_EQ|INE467B01029">INE467B01029 (ACC)</option>
      <option value="NSE_INDEX|Nifty 50">Nifty 50 Index</option>
      <option value="NSE_EQ|INE020B01018">INE020B01018</option>
      <option value="NSE_INDEX|Nifty Bank">Nifty Bank Index</option>
    </select>
  </div>

  <p>Currently viewing: <span id="current-symbol">NSE_EQ|INE467B01029</span></p>
  <div id="container">
    <canvas id="fp" width="900" height="600" style="border:1px solid #000;"></canvas>
    <canvas id="dom" width="300" height="600" style="border:1px solid #000;"></canvas>
  </div>

  <script>
    // --- Configuration ---
    let SELECTED_SYMBOL = document.getElementById('symbol-select').value;
    const fpCanvas = document.getElementById("fp");
    const fpCtx = fpCanvas.getContext("2d");
    const domCanvas = document.getElementById("dom");
    const domCtx = domCanvas.getContext("2d");

    let bars = {}; // Store bars keyed by symbol for future multi-chart use, but use SELECTED_SYMBOL for drawing.
    const LEVEL_HEIGHT = 14; 
    const TICK_SIZE = 0.05; 
    
    // Initialize the bars array for the default symbol
    bars[SELECTED_SYMBOL] = [];

    // --- WebSocket Connection ---
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onmessage = e => {
      // Data is now sent as text string due to JSON serialization fix
      const msg = JSON.parse(e.data);

      // --- CRITICAL FIX: FILTER BY SELECTED_SYMBOL ---
      if (msg.symbol !== SELECTED_SYMBOL) {
          return; 
      }

      if(msg.type === "footprint") {
        if (!bars[msg.symbol]) bars[msg.symbol] = [];
        
        // Push to the current symbol's bars
        bars[msg.symbol].push(msg);
        
        // Keep a manageable number of bars (e.g., 20 bars)
        if(bars[msg.symbol].length > 20) bars[msg.symbol].shift();
        
        drawFP(); 
      }

      if(msg.type === "dom") {
        drawDOM(msg);
      }
    };
    
    // --- Symbol Selection Handler ---
    document.getElementById('symbol-select').addEventListener('change', (e) => {
        SELECTED_SYMBOL = e.target.value;
        document.getElementById('current-symbol').textContent = SELECTED_SYMBOL;
        
        // Clear old data and start fresh draw loop for the new symbol
        bars[SELECTED_SYMBOL] = bars[SELECTED_SYMBOL] || [];
        drawFP(); 
        drawDOM({bids: {}, asks: {}}); // Clear DOM instantly
    });
    
    // --- FOOTPRINT DRAW FUNCTION (drawFP) with Dynamic Scaling Fix ---
    function drawFP() {
      const currentBars = bars[SELECTED_SYMBOL] || [];
      if (currentBars.length === 0) {
          fpCtx.clearRect(0,0,fpCanvas.width,fpCanvas.height);
          fpCtx.fillStyle = "#333";
          fpCtx.fillText("Waiting for data on " + SELECTED_SYMBOL + "...", 10, 30);
          return;
      }

      // 1. Find Price Range for Dynamic Scaling
      let minPrice = Infinity;
      let maxPrice = -Infinity;
      
      currentBars.forEach(bar => {
        Object.keys(bar.levels).forEach(priceStr => {
          const price = parseFloat(priceStr);
          minPrice = Math.min(minPrice, price);
          maxPrice = Math.max(maxPrice, price);
        });
      });

      fpCtx.clearRect(0,0,fpCanvas.width,fpCanvas.height);
      
      const BAR_WIDTH = 38;
      const BAR_SPACING = 2; 
      const max_delta = 100; 

      currentBars.forEach((bar, i) => {
        const barX = i * (BAR_WIDTH + BAR_SPACING);

        Object.entries(bar.levels).forEach(([priceStr, v]) => {
          const price = parseFloat(priceStr);

          // 2. Calculate Y position based on relative price (DYNAMIC SCALING)
          let yOffset = (price - minPrice) / TICK_SIZE * LEVEL_HEIGHT;
          let y = fpCanvas.height - yOffset - LEVEL_HEIGHT; 

          if (y < 0 || y > fpCanvas.height) return;

          // 3. Calculate Heat and Draw Box
          const heat = Math.min(Math.abs(v.abs) / max_delta, 1);
          const delta = v.ask - v.bid;

          if (delta > 0) {
            fpCtx.fillStyle = `rgba(0, 150, 0, ${0.3 + heat * 0.7})`; 
          } else if (delta < 0) {
            fpCtx.fillStyle = `rgba(150, 0, 0, ${0.3 + heat * 0.7})`; 
          } else {
            fpCtx.fillStyle = `rgba(100, 100, 100, ${0.1 + heat * 0.9})`; 
          }
          
          fpCtx.fillRect(barX, y, BAR_WIDTH, LEVEL_HEIGHT);

          // 4. Draw Text
          fpCtx.fillStyle = "#fff"; 
          fpCtx.font = "10px sans-serif";
          fpCtx.fillText(`${v.bid}|${v.ask}`, barX + 2, y + 10);
        });
      });
    }

    // --- DOM Draw Function (drawDOM) ---
    function drawDOM(msg) {
      domCtx.clearRect(0,0,domCanvas.width,domCanvas.height);
      domCtx.font = "12px monospace";
      let y = 20;

      // Draw ASKS (accessing msg.asks)
      domCtx.fillStyle = "red";
      domCtx.fillText("--- ASKS ---", 10, y);
      y += 20;
      
      // Sort asks by price descending for display order
      const sortedAsks = Object.entries(msg.asks).sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]));
      
      sortedAsks.forEach(([p, q]) => {
        domCtx.fillText(`${p.padEnd(8)} ${q}`, 10, y);
        y += 14;
      });
      
      y += 10;
      
      // Draw BIDS (accessing msg.bids)
      domCtx.fillStyle = "green";
      domCtx.fillText("--- BIDS ---", 10, y);
      y += 20;

      // Sort bids by price descending
      const sortedBids = Object.entries(msg.bids).sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]));
      
      sortedBids.forEach(([p, q]) => {
        domCtx.fillText(`${p.padEnd(8)} ${q}`, 10, y);
        y += 14;
      });
    }
  </script>
</body>
</html>



"""





@app.get("/")
async def get_html():
    return HTMLResponse(content=html_content, status_code=200)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    try:
        await ws.accept()
    except Exception as e:
        print(f"[ERROR] WebSocket accept failed: {repr(e)}")
        return 
        
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        print(f"[WS] Client disconnected naturally.")
    except Exception as e:
        print(f"[WS] Connection closed with unexpected error: {repr(e)}")
    finally:
        clients.remove(ws)

async def broadcast(msg):
    dead = []
   # FIX: Iterate over a copy of the set for thread safety/resilience
    for ws in list(clients): 
        try:
            # FIX: Use json.dumps with the custom serializer and send as text
            json_str = json.dumps(msg, default=json_serializer)
            await ws.send_text(json_str) 
        except WebSocketDisconnect:
            dead.append(ws)
        except Exception as e:
            # Explicitly handle generic exceptions to prevent loop failures
            print(f"[ERROR] Failed to send message to client: {repr(e)}")
            dead.append(ws) 
            
    for ws in dead:
        if ws in clients:
            clients.remove(ws)

# ================= WSS STREAM (Unchanged) =================
router = LiveMarketRouter()

def start_upstox_stream():
    config = upstox_client.Configuration()
    config.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(config)
    streamer = MarketDataStreamerV3(api_client, INSTRUMENTS, "full")
    streamer.on("message", router.on_message)
    streamer.on("open", lambda: print("[WSS] Connected"))
    streamer.on("error", lambda e: print("[WSS] Error:", e))
    streamer.on("close", lambda c,r: print("[WSS] Closed", c,r))
    streamer.auto_reconnect(True, 10, 5)
    print("[WSS] Starting connection...")
    streamer.connect()
    print("[WSS] Connection finished.")


# ================= BOOT =================
if __name__ == "__main__":
    print(f"[SYSTEM] Footprint engine running | WS port {WS_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=WS_PORT)