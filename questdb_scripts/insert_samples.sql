-- Sample INSERT statements for QuestDB

-- Levels
INSERT INTO levels (symbol, price, side, created_ts, last_used_ts) VALUES ('BTC-USD', 50000.0, 'buy', systimestamp(), systimestamp());
INSERT INTO levels (symbol, price, side, created_ts, last_used_ts) VALUES ('ETH-USD', 4000.0, 'sell', '2023-10-27T10:00:00.000000Z', '2023-10-27T11:00:00.000000Z');

-- Open Trades
INSERT INTO open_trades (symbol, side, entry_price, entry_ts, stop_price, tp_price, status) VALUES ('BTC-USD', 'buy', 51000.0, systimestamp(), 50500.0, 52000.0, 'OPEN');

-- Closed Trades
INSERT INTO closed_trades (symbol, side, entry_price, entry_ts, stop_price, tp_price, exit_price, exit_ts, reason, pnl, status) VALUES ('ETH-USD', 'sell', 3900.0, '2023-10-26T10:00:00.000000Z', 3950.0, 3800.0, 3850.0, '2023-10-26T11:00:00.000000Z', 'TP', 50.0, 'CLOSED');

-- Symbol State
INSERT INTO symbol_state (symbol, last_candle_ts) VALUES ('BTC-USD', '2023-10-27T12:00:00.000000Z');

-- Context Candles 15m
INSERT INTO context_candles_15m (symbol, ts, open, high, low, close, volume) VALUES ('BTC-USD', '2023-10-27T12:00:00.000000Z', 51000.0, 51100.0, 50900.0, 51050.0, 100.5);
INSERT INTO context_candles_15m (symbol, ts, open, high, low, close, volume) VALUES ('BTC-USD', '2023-10-27T12:15:00.000000Z', 51050.0, 51200.0, 51000.0, 51150.0, 120.2);

-- Ticks
INSERT INTO ticks (symbol, ts, ltp, volume, total_buy_qty, total_sell_qty) VALUES ('BTC-USD', systimestamp(), 51160.0, 1, 1000, 950);
INSERT INTO ticks (symbol, ts, ltp, volume, total_buy_qty, total_sell_qty) VALUES ('BTC-USD', systimestamp(), 51161.0, 2, 1002, 950);


-- Footprints
INSERT INTO footprints (symbol, ts, open, high, low, close, volume, levels) VALUES ('BTC-USD', '2023-10-27T12:15:00.000000Z', 51050.0, 51200.0, 51000.0, 51150.0, 120.2, '[{"price": 51100, "volume": 50.1}, {"price": 51150, "volume": 70.1}]');

-- Context Candles 60m
INSERT INTO context_candles_60m (symbol, ts, open, high, low, close, volume) VALUES ('BTC-USD', '2023-10-27T12:00:00.000000Z', 51000.0, 51500.0, 50800.0, 51450.0, 500.7);
INSERT INTO context_candles_60m (symbol, ts, open, high, low, close, volume) VALUES ('BTC-USD', '2023-10-27T13:00:00.000000Z', 51450.0, 51600.0, 51400.0, 51550.0, 450.3);
