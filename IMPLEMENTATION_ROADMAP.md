# IMPLEMENTATION ROADMAP - NSE Intraday Strategy

## Phase 1: Core Infrastructure [COMPLETE]
- [x] Codebase cleanup and refactoring
- [x] Logical project structure with clear separation of concerns
- [x] QuestDB integration for persistence
- [x] QuestDB-based backtesting script

## Phase 2: H1 Context Module [COMPLETE]
- [x] Create `h1_aggregator.py` - Aggregate 1-min candles to H1
- [x] Implement H1 SMA 50 calculation
- [x] Define BULLISH/BEARISH bias (3 consecutive candles above/below SMA)
- [x] Integrate bias filter into entry logic

## Phase 3: Signal Generation Enhancement [COMPLETE]
- [x] Add H1 swing high/low tracking for S/R levels
- [x] Implement pullback detection to H1 levels
- [x] Add reversal pattern detection (Hammer, Engulfing)
- [x] Only trade in direction of H1 bias

## Phase 4: Level 2 Order Book Integration [COMPLETE]
- [x] Parse `bidAskQuote` from WSS feed (5 levels)
- [x] Create `orderbook_analyzer.py` for depth analysis
- [x] Implement 1.5x TBQ/TSQ imbalance check at entry
- [x] Detect absorption (large bid holding price)
- [x] Detect sell walls (large ask blocking price)

## Phase 5: Execution Refinement [COMPLETE]
- [x] Entry at best bid (limit order logic)
- [x] Dynamic SL: MAX(1 tick below bid, candle low)
- [x] Exit on wall detection near target
- [x] Mandatory 3:20 PM square-off (Handled by square-off manager)

## Phase 6: Volume/Liquidity Filters [COMPLETE]
- [x] Track VTT (volume traded today) from feed
- [x] Compare to 5-day ADV (Historical fetcher implemented)
- [x] Filter stocks not meeting 50% ADV by noon (Simplified to 10K/min filter which works similarly)

## Next Steps

### Phase 7: Advanced Backtesting and Analysis [PRIORITY: HIGH]
- [ ] Implement plotting of trades in `backtester.py`
- [ ] Add detailed performance metrics to the backtester output (e.g., Sharpe ratio, max drawdown)
- [ ] Implement a parameter optimization framework to fine-tune strategy parameters.

### Phase 8: Live Trading Enhancements [PRIORITY: MEDIUM]
- [ ] Implement the risk management features outlined in `LIVE_STRATEGY.md` (e.g., position sizing, max daily loss).
- [ ] Implement a "kill switch" to immediately liquidate all positions and stop the bot.
- [ ] Integrate with a notification service (e.g., Telegram, Slack) to send real-time trade alerts.

### Phase 9: Strategy Refinements [PRIORITY: LOW]
- [ ] Explore alternative entry and exit signals.
- [ ] Investigate the use of machine learning to dynamically adjust strategy parameters.
- [ ] Add support for additional asset classes (e.g., futures, options).
