# AUCTION THEORY TRADING BOT

This project is a trading bot that uses Auction Market Theory to make trading decisions. The core of the strategy is a `VolumeProfile` class that calculates the Value Area (VA) and Point of Control (POC) from a rolling window of candle data to determine the market regime.

## Trading Strategy

The trading strategy is based on a regime-aware model that adapts to the current market structure, as identified by the `VolumeProfile` in `auction_theory.py` and implemented in the `AuctionContext` class in `stage9_context.py`.

The bot distinguishes between two primary market regimes:

-   **Balanced Market (Mean Reversion):** When the volume profile is bell-shaped and balanced, the bot favors mean-reversion trades.
    -   **Long Trades:** Entered when the price is at or below the Value Area Low (VAL).
    -   **Short Trades:** Entered when the price is at or above the Value Area High (VAH).

-   **Unbalanced Market (Trend Following):** When the volume profile is skewed, indicating a trend, the bot favors trend-following trades.
    -   **Long Trades:** In a bullish trend (where the Point of Control is in the upper half of the value area), long trades are entered on pullbacks to the POC.
    -   **Short Trades:** In a bearish trend (where the Point of Control is in the lower half of the value area), short trades are entered on rallies to the POC.

This regime-based approach is designed to correct the "wrong side bias" of simpler models and align the bot's behavior with the principles of Auction Market Theory.

## Backtesting

The `main.py` script is used for backtesting the trading strategy. It reads from a series of `.gz` files that contain historical tick data, and it simulates a live WebSocket feed to the trading engine. The backtesting script requires a running MongoDB instance to store and retrieve trade data.

### Prerequisites

-   Python 3
-   MongoDB

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

3.  Install and start MongoDB. On a Debian/Ubuntu system, you can do this with the following commands:
    ```bash
    # Import the GPG key
    curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor

    # Create the package list file
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list

    # Update the package manager and install MongoDB
    sudo apt-get update
    sudo apt-get install -y mongodb-org

    # Start the MongoDB service
    sudo systemctl start mongod
    ```

### Running the Backtest

To run the backtest, you will need to have a running MongoDB instance. You can then run the following command:

```bash
python3 main.py
```

The backtesting script will then process the data in the `.gz` files and print the results of the trading strategy to the console.

## Live Trading

The `main_live.py` script is used to run the trading bot in a live market environment. It connects to the Upstox WebSocket feed to receive real-time market data.

### Prerequisites

-   An Upstox trading account
-   An Upstox API access token

### Configuration

1.  Open the `main_live.py` file.
2.  Replace the placeholder `"YOUR_TOKEN_HERE"` with your actual Upstox API access token:
    ```python
    ACCESS_TOKEN = "your-upstox-access-token"
    ```

### Running the Live Trading Bot

To run the live trading bot, execute the following command:

```bash
python3 main_live.py
```

The bot will then connect to the Upstox WebSocket feed, and the monitor will print a summary of open and closed trades to the console every 5 seconds.
