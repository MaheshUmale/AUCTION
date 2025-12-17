CREATE TABLE IF NOT EXISTS levels (
    symbol SYMBOL,
    price DOUBLE,
    side SYMBOL,
    created_ts TIMESTAMP,
    last_used_ts TIMESTAMP
) timestamp(created_ts);

CREATE TABLE IF NOT EXISTS open_trades (
    symbol SYMBOL,
    side SYMBOL,
    entry_price DOUBLE,
    entry_ts TIMESTAMP,
    stop_price DOUBLE,
    tp_price DOUBLE,
    status SYMBOL
) timestamp(entry_ts);

CREATE TABLE IF NOT EXISTS closed_trades (
    symbol SYMBOL,
    side SYMBOL,
    entry_price DOUBLE,
    entry_ts TIMESTAMP,
    stop_price DOUBLE,
    tp_price DOUBLE,
    exit_price DOUBLE,
    exit_ts TIMESTAMP,
    reason SYMBOL,
    pnl DOUBLE,
    status SYMBOL
) timestamp(exit_ts);

CREATE TABLE IF NOT EXISTS symbol_state (
    symbol SYMBOL,
    last_candle_ts TIMESTAMP
) timestamp(last_candle_ts);

CREATE TABLE IF NOT EXISTS context_candles_15m (
    symbol SYMBOL,
    ts TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE
) timestamp(ts);

CREATE TABLE IF NOT EXISTS ticks (
    symbol SYMBOL,
    ts TIMESTAMP,
    ltp DOUBLE,
    volume LONG,
    total_buy_qty LONG,
    total_sell_qty LONG
) timestamp(ts);

CREATE TABLE IF NOT EXISTS footprints (
    symbol SYMBOL,
    ts TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    levels STRING
) timestamp(ts);

CREATE TABLE IF NOT EXISTS context_candles_60m (
    symbol SYMBOL,
    ts TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE
) timestamp(ts);
