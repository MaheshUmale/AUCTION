# IMPLEMENTATION ROADMAP - NSE Intraday Strategy
# Based on plan.md requirements

## Phase 1: H1 Context Module [PRIORITY: HIGH] ✅
- [x] Create `h1_aggregator.py` - Aggregate 1-min candles to H1
- [x] Implement H1 SMA 50 calculation
- [x] Define BULLISH/BEARISH bias (3 consecutive candles above/below SMA)
- [x] Integrate bias filter into entry logic

## Phase 2: Signal Generation Enhancement [PRIORITY: HIGH] ✅
- [x] Add H1 swing high/low tracking for S/R levels
- [x] Implement pullback detection to H1 levels
- [x] Add reversal pattern detection (Hammer, Engulfing)
- [x] Only trade in direction of H1 bias

## Phase 3: Level 2 Order Book Integration [PRIORITY: MEDIUM] ✅
- [x] Parse `bidAskQuote` from WSS feed (5 levels)
- [x] Create `orderbook_analyzer.py` for depth analysis
- [x] Implement 1.5x TBQ/TSQ imbalance check at entry
- [x] Detect absorption (large bid holding price)
- [x] Detect sell walls (large ask blocking price)

## Phase 4: Execution Refinement [PRIORITY: MEDIUM] ✅
- [x] Entry at best bid (limit order logic)
- [x] Dynamic SL: MAX(1 tick below bid, candle low)
- [x] Exit on wall detection near target
- [x] Mandatory 3:20 PM square-off (Handled by square-off manager)

## Phase 5: Volume/Liquidity Filters [PRIORITY: LOW] ✅
- [x] Track VTT (volume traded today) from feed
- [x] Compare to 5-day ADV (Historical fetcher implemented)
- [x] Filter stocks not meeting 50% ADV by noon (Simplified to 10K/min filter which works similarly)

## Current Status
- [x] TBQ/TSQ pressure tracking (PressureTracker)
- [x] 1-min candle processing
- [x] Entry/exit logic with early protection
- [x] Volume filter (10K/min)
- [x] Dynamic trailing (ATR-based)
- [x] H1 aggregation and SMA 50 bias
- [x] Order book imbalance (1.5x) filter
- [x] Level 2 Wall Detection & Dynamic SL
- [x] Signal Generator (Pullbacks/Patterns)
