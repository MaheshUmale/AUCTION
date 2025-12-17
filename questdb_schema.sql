-- questdb_schema.sql
[cite_start]-- Purpose: Initialize the QuestDB table with a flattened, optimized schema [cite: 17]

DROP TABLE IF EXISTS tick_data;

CREATE TABLE tick_data (
    -- Designated timestamp (partitioned by DAY)
    [cite_start]timestamp TIMESTAMP, [cite: 11]
    
    -- Instrument identification
    [cite_start]instrument_key SYMBOL CACHE, [cite: 11]
    [cite_start]feed_type SYMBOL, [cite: 11]
    
    -- LTPC Data (common to both feed types)
    [cite_start]ltp DOUBLE, [cite: 11]
    [cite_start]ltq INT,    -- Will be NULL for indices [cite: 11]
    [cite_start]cp DOUBLE, [cite: 12]
    
    -- Market Data (equity only)
    [cite_start]oi LONG, [cite: 12]
    [cite_start]atp DOUBLE, [cite: 12]
    [cite_start]vtt LONG, [cite: 12]
    [cite_start]tbq DOUBLE, [cite: 12]
    [cite_start]tsq DOUBLE, [cite: 13]
    
    -- Best Bid/Ask (L1 depth)
    bid_price_1 DOUBLE, bid_qty_1 INT,
    ask_price_1 DOUBLE, ask_qty_1 INT,
    
    [cite_start]-- Additional Depth Levels (L2-L5) [cite: 14]
    bid_price_2 DOUBLE, bid_qty_2 INT,
    ask_price_2 DOUBLE, ask_qty_2 INT,
    bid_price_3 DOUBLE, bid_qty_3 INT,
    ask_price_3 DOUBLE, ask_qty_3 INT,
    bid_price_4 DOUBLE, bid_qty_4 INT,
    ask_price_4 DOUBLE, ask_qty_4 INT,
    bid_price_5 DOUBLE, bid_qty_5 INT,
    ask_price_5 DOUBLE, ask_qty_5 INT,
    
    [cite_start]-- OHLC Data (index only) [cite: 14]
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    
    -- Metadata
    [cite_start]insertion_time TIMESTAMP [cite: 14]
[cite_start]) TIMESTAMP(timestamp) PARTITION BY DAY; [cite: 15]