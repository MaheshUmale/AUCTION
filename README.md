# AUCTION THEORY TRADING BOT

This project is a trading bot that uses Auction Market Theory to make trading decisions. The core of the strategy is a `VolumeProfile` class that calculates the Value Area (VA) and Point of Control (POC) from a rolling window of candle data to determine the market regime.

## Project Structure

The project is organized into the following directories:

-   `trading_core`: Contains the core components of the trading engine, including the `LiveAuctionEngine`, data models, and persistence layer.
-   `data_handling`: Includes modules for fetching and processing historical data.
-   `strategy`: Contains the implementation of the trading strategy, including the `AuctionContext` and other strategy components.
-   `ui`: Includes the Flask-based UI for monitoring trades.
-   `utils`: Contains utility scripts for analyzing backtest results.

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

The `backtester.py` script is used for backtesting the trading strategy. It queries historical tick data from a QuestDB instance and simulates a live WebSocket feed to the trading engine.

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
python3 backtester.py --symbol <symbol> --from-date <YYYY-MM-DD> --to-date <YYYY-MM-DD>
```

The backtesting script will then process the data and print a summary of the trading strategy's performance to the console.

## Live Trading

The `main_live.py` script is used to run the trading bot in a live market environment. It connects to the Upstox WebSocket feed to receive real-time market data.

### Prerequisites

-   An Upstox trading account
-   An Upstox API access token

### Configuration

1.  Open the `config.py` file.
2.  Replace the placeholder `"your_access_token"` with your actual Upstox API access token.

### Running the Live Trading Bot

To run the live trading bot, execute the following command:

```bash
python3 main_live.py
```

The bot will then connect to the Upstox WebSocket feed, and the monitor will print a summary of open and closed trades to the console every 5 seconds.

## Dataflow and Replay

The trading bot is designed to store all incoming WebSocket feed data in a raw format, which allows for high-fidelity backtesting and replay of market data. This is achieved by storing the raw JSON data from the WebSocket feed in the `raw_wss_feed` table in the QuestDB database.

### Data Storage

-   **Table:** `raw_wss_feed`
-   **Columns:**
    -   `ts`: The timestamp of the message, in nanoseconds.
    -   `raw_json`: The raw JSON data from the WebSocket feed, as a string.

### Data Replay

The data stored in the `raw_wss_feed` table can be used to rehydrate the trading engine and replay the market data for backtesting or analysis. This is done by querying the table for a specific time range and then feeding the `raw_json` data back into the `LiveMarketRouter.on_message` method. This allows for a more accurate simulation of live market conditions, as it includes all the nuances of the real-time data feed.
