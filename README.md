# AUCTION THEORY TRADING BOT

This project is a trading bot that uses Auction Market Theory to make trading decisions. The core of the strategy is a `VolumeProfile` class that calculates the Value Area (VA) and Point of Control (POC) from a rolling window of candle data.

## Trading Strategy

The trading strategy is based on a mean-reversion approach to the Value Area. The `AuctionContext` class in `stage9_context.py` uses the `VolumeProfile` to identify high-probability trades at the edges of the value area.

-   **Long Trades:** Long trades are favored when the price is near the Value Area Low (VAL).
-   **Short Trades:** Short trades are favored when the price is near the Value Area High (VAH).

The proximity to the VA is determined by the `vah_proximity_threshold` and `val_proximity_threshold` parameters in the `allow_trade` method of the `AuctionContext` class. These parameters are expressed as a percentage of the Value Area, and they can be adjusted to make the trading strategy more or less restrictive.

## Backtesting

The `main.py` script is used for backtesting the trading strategy. It reads from a series of `.gz` files that contain historical tick data, and it simulates a live WebSocket feed to the trading engine. The backtesting script requires a running MongoDB instance to store and retrieve trade data.

## Running the Backtest

To run the backtest, you will need to have a running MongoDB instance. You can then run the following command:

```bash
python3 main.py
```

The backtesting script will then process the data in the `.gz` files and print the results of the trading strategy to the console.
