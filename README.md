# AUCTION THEORY TRADING BOT

This project is a trading bot that uses Auction Market Theory to make trading decisions. The core of the strategy is a `VolumeProfile` class that calculates the Value Area (VA) and Point of Control (POC) from a rolling window of candle data to determine the market regime.

## Project Structure

The project is organized into the following directories:

-   `api`: Contains the FastAPI backend for the UI.
-   `configs`: Contains the strategy configuration files.
-   `data_handling`: Includes modules for fetching and processing historical data.
-   `frontend`: Contains the HTML and JavaScript for the UI.
-   `scripts`: Contains the core services for data ingestion, persistence, and strategy management.
-   `strategy`: Contains the implementation of the trading strategy.
-   `trading_core`: Contains the core components of the trading engine, including the `LiveAuctionEngine`, data models, and persistence layer.

## Trading Strategy

The trading strategy is based on a regime-aware model that adapts to the current market structure, as identified by the `VolumeProfile` in `strategy/auction_theory.py` and implemented in the `AuctionContext` class in `strategy/stage9_context.py`.

The bot distinguishes between two primary market regimes:

-   **Balanced Market (Mean Reversion):** When the volume profile is bell-shaped and balanced, the bot favors mean-reversion trades.
-   **Unbalanced Market (Trend Following):** When the volume profile is skewed, indicating a trend, the bot favors trend-following trades.

## Running the System

The new architecture is a multi-process system with several services that work together. A single `run.py` script is provided to launch and manage all the necessary services.

### Prerequisites

-   Python 3
-   Docker
-   An Upstox trading account and a valid API access token.

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

3.  Install and start QuestDB using Docker:
    ```bash
    sudo docker run -d -p 9000:9000 -p 8812:8812 questdb/questdb
    ```

### Configuration

1.  Open the `config.py` file.
2.  Replace the placeholder `ACCESS_TOKEN` with your actual Upstox API access token.
3.  Modify the `WATCHLIST` and other strategy parameters as needed.

### Launching the System

To run the entire trading system, execute the following command from the project root:

```bash
python3 run.py
```

This will launch the following services:

-   **Data Ingestor (`scripts/ingestor.py`):** Connects to the Upstox WebSocket, fetches real-time market data, and publishes it to a ZeroMQ message bus.
-   **Persistence Service (`scripts/persistor.py`):** Subscribes to the ZeroMQ bus and saves all incoming market data to the QuestDB database.
-   **Strategy Manager (`scripts/strategy_manager.py`):** Loads the strategy configurations from `configs/strategies.json` and launches each strategy in a separate process.
-   **API Server (`api/server.py`):** A FastAPI server that subscribes to the ZeroMQ bus and broadcasts market data to the frontend via a WebSocket.

### Accessing the UI

Once the system is running, you can access the real-time trading dashboard by opening a web browser and navigating to:

```
http://localhost:8000
```

The dashboard will display a live candlestick chart of the instruments defined in your watchlist.

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
