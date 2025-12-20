# AUCTION THEORY TRADING BOT

This project is a high-performance, multi-process, service-oriented trading bot that uses Auction Market Theory to make trading decisions. The system is designed for intraday options trading and features a modular architecture that allows for parallel strategy execution and real-time data visualization.

## Architecture

The system follows a "Omni-Flow" architecture, which is a multi-process, service-oriented model built around a ZeroMQ message bus. This design decouples the core services, allowing for high-speed, asynchronous communication and improved fault tolerance.

The three core services are:

-   **Data Ingestor:** Captures real-time market data and distributes it to the rest of the system.
-   **Strategy Manager:** Executes trading strategies in parallel, isolated processes.
-   **API Server:** Serves the frontend UI and streams real-time data to the browser.

### Data Flow Diagram

```
+-----------------+      +------------------+      +-------------------+
| Upstox WebSocket|----->|  Data Ingestor   |----->|   ZeroMQ Broker   |
+-----------------+      +------------------+      +-------------------+
                         |                  |      |                   |
                         | (Publishes Data) |      | (Distributes Data)|
                         +------------------+      +-------------------+
                               |                   /|\                |
                               |                    |                 |
                               V                    |                 V
                         +------------------+      |           +-------------------+
                         |      DuckDB      |<-----+           |  Strategy Manager |
                         +------------------+                  +-------------------+
                               (Persists Data)                   (Subscribes to Data)
                                                                       |
                                                                       |
                                                                       V
                                                                +----------------+
                                                                | API/Web Server |
                                                                +----------------+
                                                                (Subscribes to Data)
                                                                       |
                                                                       |
                                                                       V
                                                                +--------------+
                                                                |   Frontend   |
                                                                +--------------+
                                                                (Receives Data)
```

## Data Flow

The data flow is designed to be fast, efficient, and reliable:

1.  **Data Ingestion:** The `ingestor` service connects to the Upstox WebSocket and captures real-time market data, including ticks, candles, and order book updates.

2.  **Distribution & Persistence:** The `ingestor` simultaneously publishes the raw data to a ZeroMQ topic and persists it to a local DuckDB file for high-speed analytical queries.

3.  **Strategy Consumption:** The `strategy_manager` launches each trading strategy in a separate process. Each process subscribes to the ZeroMQ topic to receive the live data feed and generate trading signals.

4.  **Frontend Visualization:** The `api/server` hosts the frontend UI and provides a WebSocket endpoint that subscribes to the ZeroMQ bus, forwarding all real-time data and signals to the browser for visualization.

## Components

### `run.py`

This is the main entry point of the application. It launches and manages the three core services: `ingestor`, `strategy_manager`, and `api/server`. It also handles graceful shutdown and restarts any services that fail unexpectedly.

### `scripts/ingestor.py`

The data ingestor is a multithreaded service that:

-   Connects to the Upstox WebSocket to receive real-time market data.
-   Publishes the data to a ZeroMQ message bus for distribution to other services.
-   Persists the data to a local DuckDB database for historical analysis and backtesting.

### `scripts/strategy_manager.py`

The strategy manager is a multi-process service that:

-   Loads trading strategy configurations from `configs/strategies.json`.
-   Launches each strategy in a separate, isolated process to ensure parallel execution and fault tolerance.
-   Monitors the health of the strategy processes and restarts them if they fail.

### `api/server.py`

The API server is a FastAPI application that:

-   Serves the frontend UI (`frontend/index.html`).
-   Provides a WebSocket endpoint that subscribes to the ZeroMQ bus and streams real-time data to the browser.
-   Manages client connections and broadcasts data to all connected clients.

## File Descriptions

-   **`api/`:** Contains the FastAPI backend server.
-   **`configs/`:** Includes configuration files, such as `strategies.json`, which defines the trading strategies to be executed.
-   **`data/`:** Stores historical data for backtesting.
-   **`data_handling/`:** Contains modules for processing and saving feed data.
-   **`frontend/`:** Includes the HTML, CSS, and JavaScript files for the frontend UI.
-   **`scripts/`:** Includes the core service scripts (`ingestor.py`, `strategy_manager.py`) and other utility scripts.
-   **`strategy/`:** Contains the implementation of the trading strategies.
-   **`trading_core/`:** Includes the core components of the trading engine, such as the `LiveAuctionEngine` and persistence layer.
-   **`ui/`:** Contains the Flask-based UI for monitoring trades.
-   **`utils/`:** Includes utility scripts for analyzing backtest results.
-   **`config.py`:** A global, untracked configuration file for sensitive information, such as API access tokens.

## Getting Started

### Prerequisites

-   Python 3

### Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install Python dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  **Create `config.py`:** Create a `config.py` file in the root directory and add the following, replacing the placeholder values with your actual credentials and settings:

    ```python
    # -- Upstox API Credentials --
    ACCESS_TOKEN = "your_upstox_access_token"

    # -- Watchlist --
    WATCHLIST = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]

    # -- Database Path --
    DUCKDB_PATH = "trading_data.duckdb" # Use ":memory:" for an in-memory database

    # -- ZeroMQ Configuration --
    ZMQ_PUB_URL = "tcp://127.0.0.1:5555"
    ZMQ_TOPIC = "market_data"
    ```

2.  **Configure Strategies:** Open `configs/strategies.json` to define the trading strategies you want to run. Each strategy is defined as a JSON object with a `name` and other strategy-specific parameters.

### Running the Application

To run the entire trading system, execute the following command from the root directory:

```bash
python3 run.py
```

This will launch the data ingestor, strategy manager, and API server. You can then access the frontend UI by navigating to `http://localhost:8000` in your web browser.
