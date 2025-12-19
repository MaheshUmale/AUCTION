# AUCTION THEORY TRADING BOT

This project is a trading bot that uses Auction Market Theory to make trading decisions. The core of the strategy is a `VolumeProfile` class that calculates the Value Area (VA) and Point of Control (POC) from a rolling window of candle data to determine the market regime.

## Project Structure

The project is organized into the following directories:

-   `trading_core`: Contains the core components of the trading engine, including the `LiveAuctionEngine`, data models, and persistence layer.
-   `data_handling`: Includes modules for fetching and processing historical data.
-   `strategy`: Contains the implementation of the trading strategy, including the `AuctionContext` and other strategy components.
-   `ui`: Includes the Flask-based UI for monitoring trades.
-   `utils`: Contains utility scripts for analyzing backtest results.
-   `data`: Contains historical data files for backtesting.
-   `scripts`: Contains standalone scripts for various tasks, such as backtesting, live trading, and data management.

## Trading Strategy

The trading strategy is based on a regime-aware model that adapts to the current market structure, as identified by the `VolumeProfile` in `strategy/auction_theory.py` and implemented in the `AuctionContext` class in `strategy/stage9_context.py`.

The bot distinguishes between two primary market regimes:

-   **Balanced Market (Mean Reversion):** When the volume profile is bell-shaped and balanced, the bot favors mean-reversion trades.
    -   **Long Trades:** Entered when the price is at or below the Value Area Low (VAL).
    -   **Short Trades:** Entered when the price is at or above the Value Area High (VAH).

-   **Unbalanced Market (Trend Following):** When the volume profile is skewed, indicating a trend, the bot favors trend-following trades.
    -   **Long Trades:** In a bullish trend (where the Point of Control is in the upper half of the value area), long trades are entered on pullbacks to the POC.
    -   **Short Trades:** In a bearish trend (where the Point of Control is in the lower half of the value area), short trades are entered on rallies to the POC.

This regime-based approach is designed to correct the "wrong side bias" of simpler models and align the bot's behavior with the principles of Auction Market Theory.

## Backtesting

The `backtester.py` script, located in the `scripts` directory, is used for backtesting the trading strategy. It queries historical tick data from a QuestDB instance and simulates a live WebSocket feed to the trading engine.

### Prerequisites

-   Python 3
-   QuestDB

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3.  Install and start QuestDB. You can do this with Docker:
    ```bash
    docker run -p 9000:9000 -p 8812:8812 questdb/questdb
    ```

### Running the Backtest

To run the backtest, you will need to have a running QuestDB instance with historical tick data. You can then run the following command:

```bash
python3 scripts/backtester.py --symbol <symbol> --from-date <YYYY-MM-DD> --to-date <YYYY-MM-DD>
```

The backtesting script will then process the data and print a summary of the trading strategy's performance to the console.

## Live Trading

The `main_live.py` script, located in the `scripts` directory, is used to run the trading bot in a live market environment. It connects to the Upstox WebSocket feed to receive real-time market data.

### Prerequisites

-   An Upstox trading account
-   An Upstox API access token

### Configuration

1.  Open the `config.py` file.
2.  Replace the placeholder `"your_access_token"` with your actual Upstox API access token.

### Running the Live Trading Bot

To run the live trading bot, execute the following command:

```bash
python3 scripts/main_live.py
```

The bot will then connect to the Upstox WebSocket feed, and the monitor will print a summary of open and closed trades to the console every 5 seconds.

## Scripts

The `scripts` directory contains a collection of standalone Python scripts for various tasks related to the trading bot. Here's a brief overview of the most important ones:

-   `backtester.py`: The main script for running backtests of the trading strategy.
-   `main_live.py`: The main script for running the trading bot in a live market environment.
-   `backfill_ticks.py`: A script for backfilling historical tick data from an external source into QuestDB.
-   `debug_db.py`: A utility script for debugging and inspecting the contents of the QuestDB database.
-   `rehydrate_history.py`: A script for rehydrating historical data from a file into the database.

## Dataflow and Replay

The trading bot is designed to store all incoming WebSocket feed data in a structured format, which allows for efficient querying and high-fidelity backtesting. All feed data, including ticks, candles, and order book updates, is stored in the `tick_data` table in QuestDB.

### Data Storage

-   **Table:** `tick_data`
-   **Schema:** The table stores various fields from the WebSocket feed, including LTP, LTQ, open, high, low, close, and order book data. A `feed_type` column distinguishes between different types of data (e.g., `TICK`, `CANDLE_I1`).






# NEXT STEPS : FOR JULES


This master plan is designed for a unified, high-performance intraday options trading platform tailored for a single machine (16GB RAM, i5, Windows 11). To meet your requirement for speed without the overhead of Redis/Mongo, we will use a Memory-First, Persistence-Later architecture.

Master Architecture: The "Omni-Flow" Engine
The system will operate using a Producer-Consumer model powered by ZeroMQ (IPC/Inproc) and QuestDB.

In-Memory Bus: ZeroMQ will handle the ultra-fast distribution of ticks from the Upstox thread to the Strategy threads.

Data Lake: QuestDB will handle high-speed ingestion (>100k rows/sec) for historical analysis and real-time state recovery.

Parallelism: Each strategy will run as a separate Process (not just a thread) to bypass the Python Global Interpreter Lock (GIL), ensuring true parallel execution for 250+ symbols.

Phase 1: High-Speed Data Pipeline (The Arteries)
The goal is to move data from Upstox to the CPU as fast as possible.

1.1 Multithreaded Ingestor: * Thread A (WSS): Captures Upstox WebSockets. It doesn't process; it just pushes raw data into a ZeroMQ PUB socket.

Thread B (QuestDB Writer): Subscribes to the ZeroMQ socket and writes ticks to QuestDB using the ILP (InfluxDB Line Protocol) for maximum throughput.

1.2 Schema Design (QuestDB):

ticks: symbol, price, volume, oi, timestamp (Designated as TIMESTAMP for ASOF Joins).

signals: strategy_id, symbol, side, price, timestamp.

1.3 Data Provider: A "Snapshot Service" that allows strategy processes to fetch the last 50 candles instantly on startup from QuestDB.

Phase 2: Strategy Orchestrator (The Brain)
This phase allows parallel strategy execution and dynamic control.

2.1 The "Swarmer" Model: * Instead of one giant loop, we launch a StrategyProcessManager.

Each strategy is a multiprocessing.Process that listens to the ZeroMQ feed.

Benefit: If Strategy A crashes or is "Stopped" by you, others continue unaffected.

2.2 Hot-Swappable Logic:

Use importlib to reload strategy classes from the strategies/ folder without killing the main server.

A JSON/YAML config will define which symbols/timeframes each strategy process should "listen" to.

Phase 3: Logic & Specialized Charts (The Heavy Lifting)
You mentioned 1-sec Renko and Volume Bubbles. Here is the optimized "Split-Logic" approach:

3.1 Backend Pre-Processing:

The strategy engine calculates Renko Bricks on-the-fly. Instead of sending 1,000 ticks to the UI, it only sends a "New Brick" event (e.g., {"type": "RENKO", "brick": "UP", "price": 24500}).

3.2 Simulated Execution (Paper Trading):

A dedicated PaperBroker class. It manages a virtual wallet.

Slippage Simulation: Adds a 0.05% slippage to orders to give you realistic results.

Logs all trades to a paper_trades table in QuestDB for end-of-day (EOD) analysis.

Phase 4: Interactive Dashboard (The Nerve Center)
We will use FastAPI for the backend and TradingView Lightweight Charts for the frontend.

4.1 Signal Stream: A WebSocket pushes strategy signals directly to your browser.

4.2 On-Demand Charting (Your Suggestion):

When you click a symbol, the Frontend requests only the last 5 minutes of tick data.

Volume Bubble Chart: Rendered using D3.js or Highcharts on the frontend.

Renko Logic: The browser handles the final visual rendering, but the Backend provides the "Brick Size" logic.

4.3 Command Center: Buttons on the UI to Start/Stop specific strategies via REST API calls to the Process Manager.

Phase 5: Integration & Verification
5.1 Unified Entry Point: A run_all.py script that uses subprocess to boot:

QuestDB (Local Instance)

Data Ingestor

Strategy Swarmer

FastAPI Server

5.2 Performance Profiling: Monitor RAM usage. 16GB is plenty, but we will use slots in Python classes to keep the memory footprint small for 250 symbols.

Summary Table: Technology Choice
Component	Technology	Reason
Data Storage	QuestDB	Optimized for time-series; supports SQL.
Messaging	ZeroMQ	Sub-millisecond latency; no server required.
API/Backend	FastAPI	Asynchronous, built-in WebSocket support.
Charting	Lightweight Charts	Fastest library for real-time tick/Renko data.
Parallelism	Multiprocessing	bypasses GIL for true concurrent strategy execution.

Export to Sheets

Next Step
Would you like me to write the boilerplate code for the ZeroMQ Data Ingestor that connects to Upstox and pushes data to the QuestDB ILP port?

### Data Replay

The structured data in the `tick_data` table can be queried to reconstruct the market state at any given time. This allows for accurate backtesting and analysis by replaying historical data through the trading engine.
