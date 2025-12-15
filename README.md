# AUCTION
Trade based on auction theory
1. Core Philosophy (Locked)

Market structure & intent come ONLY from candles

Ticks are used ONLY for exits (SL / trailing / time)

No structure, no intent, no entry logic from ticks

Zero HFT behavior; low-frequency, selective trades

Zero conceptual abstractions — only concrete, executable code

2. Data Sources
WSS (Upstox)

Continuous tick feed

Also provides 1-minute candle snapshots via:

feeds → fullFeed → marketOHLC → ohlc → interval == "I1"


Candle snapshot is authoritative

No need to reconstruct candles from ticks

REST

Historical candles (used only for backfill / restart if needed)

Live system relies on WSS candle snapshots

3. Canonical Data Models
Candle
@dataclass
class Candle:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int   # candle close timestamp (ms)

Tick
@dataclass
class Tick:
    symbol: str
    ltp: float
    ts: int   # use ltt, normalized

StructureLevel
@dataclass
class StructureLevel:
    symbol: str
    price: float
    side: str              # "LONG" or "SHORT"
    created_ts: int
    last_used_ts: Optional[int] = None

Trade
@dataclass
class Trade:
    symbol: str
    side: str              # "LONG" / "SHORT"
    entry_price: float
    entry_ts: int
    stop_price: float
    exit_price: Optional[float] = None
    exit_ts: Optional[int] = None
    reason: Optional[str] = None

4. Stage Responsibilities (Critical)
LiveMarketRouter

Parses Upstox WSS JSON

Handles multi-symbol packets

Routes:

Ticks → engine.on_tick(tick)

Candle snapshots → engine.on_candle_close(candle)

Normalizes timestamps

No strategy logic

LiveAuctionEngine (Orchestrator)

Owns:

structure levels per symbol

last candle ts per symbol

Calls:

entry logic on candle close only

exit logic via Stage-12 on ticks

NEVER executes exits directly

TradeEngine (Authoritative – NON-NEGOTIABLE)

The ONLY place allowed to:

enter trades

exit trades

persist trades

update bias guard

apply cooldown

maintain open / closed trades

All exits MUST pass through:

TradeEngine.exit_trade(...)

5. Entry Logic (Locked)

Evaluated ONLY on candle close

One trade per symbol

Uses unused structure levels only

Example:

if lvl.last_used_ts is None \
   and not trade_engine.has_open_trade(symbol):

    if lvl.side == "LONG" and candle.close > lvl.price:
        enter LONG

    elif lvl.side == "SHORT" and candle.close < lvl.price:
        enter SHORT


After entry:

lvl.last_used_ts = candle.ts

6. Exit Logic (Stage-12 – VERY IMPORTANT)
Rules

Ticks manage exits only

Stage-12:

does NOT call persistence

does NOT call bias guard

does NOT call cooldown

does NOT call exit_trade

Stage-12 returns an ExitSignal

ExitSignal(symbol, price, ts, reason)

LiveAuctionEngine.on_tick
signal = stage12.on_tick(trade, tick)
if signal:
    trade_engine.exit_trade(...)

7. Stop Logic (Stage-12)

Initial stop is computed ON ENTRY

Stored in trade.stop_price

Stage-12:

only reads & updates trade.stop_price

NEVER recomputes from scratch

No compute_stop() API exists

8. Timestamp Rules (Critical Bug Fix)

Exit timestamp MUST be:

exit_ts = max(tick.ts, trade.entry_ts)


Prevents “exit before entry” bug

9. Persistence (MongoDB)
Stored Collections

open_trades

closed_trades

structure_levels

Rehydration Rules

On restart:

load open trades

load structure levels

Convert Mongo dicts → dataclass objects

Strip _id before rehydration

10. Observations from Live Trading (Validated)

~168 trades across ~250 symbols = NOT overtrading

Only ~20 symbols traded → GOOD selectivity

Entries mostly at correct locations

Wrong side bias → to be corrected

Many SL hits due to tight stops → volatility normalization required

11. Current Stage Status

✅ Stage-8: Live WSS routing + execution

✅ Stage-9/10: Directional wiring

🔄 Stage-12: Stop distance normalization (in progress)

❌ Stage-13: Trade lifecycle hardening (next)

❌ Stage-14: Risk & exposure control (next)

12. Remaining Stages (Clear Roadmap)
Stage-13: Trade Lifecycle Hardening

One exit per trade (idempotent)

Re-entry cooldown enforcement

No duplicate close calls

Stage-14: Risk Control

Max concurrent trades

Per-symbol exposure cap

Optional sector limits

13. Non-Negotiables

No conceptual names

No assumed APIs

No fuzzy abstractions

If a class / method is unknown → ASK

Concrete, runnable code only
