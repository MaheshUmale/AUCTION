# Live Intraday Trading Strategy

This document outlines a strategic plan for deploying the Auction Theory Trading Bot in a live intraday trading environment.

## 1. Pre-Flight Checks

Before deploying the bot in a live market, the following pre-flight checks must be completed:

-   **Connectivity:** Ensure a stable and low-latency connection to the Upstox WebSocket feed.
-   **Authentication:** Verify that the Upstox API access token is valid and has the necessary permissions for live trading.
-   **Configuration:** Double-check all the configuration settings in `config.py`, including the watchlist and any strategy-specific parameters.
-   **System Health:** Monitor the system's CPU, memory, and network usage to ensure it can handle the demands of live trading.

## 2. Risk Management

Effective risk management is crucial for long-term success in live trading. The following risk management strategies will be implemented:

-   **Position Sizing:** The position size for each trade will be calculated based on a fixed percentage of the account balance (e.g., 1-2%).
-   **Stop-Loss Orders:** A hard stop-loss order will be placed for every trade to limit the maximum potential loss. The stop-loss level will be determined by the `Stage12Controller` based on market volatility.
-   **Max Daily Loss:** A maximum daily loss limit will be set (e.g., 5% of the account balance). If this limit is reached, the bot will automatically stop trading for the day.
-   **Kill Switch:** A manual "kill switch" will be implemented to immediately liquidate all open positions and stop the bot in case of a critical error or unexpected market event.

## 3. Performance Monitoring

The bot's performance will be continuously monitored to identify areas for improvement. The following metrics will be tracked:

-   **Win Rate:** The percentage of profitable trades.
-   **Profit Factor:** The gross profit divided by the gross loss.
-   **Sharpe Ratio:** A measure of risk-adjusted return.
-   **Maximum Drawdown:** The largest peak-to-trough decline in the account balance.

These metrics will be tracked on a daily, weekly, and monthly basis. The results will be used to refine the trading strategy and risk management parameters.

## 4. Gradual Rollout

The bot will be deployed in a phased approach to minimize risk:

1.  **Paper Trading:** The bot will initially be deployed in a paper trading environment to validate its performance in real-time market conditions.
2.  **Small-Scale Live Trading:** Once the bot has demonstrated consistent profitability in paper trading, it will be deployed in a live account with a small amount of capital.
3.  **Full-Scale Live Trading:** After a successful trial period with a small-scale deployment, the bot will be deployed with the full intended capital.

This gradual rollout will allow for any issues to be identified and resolved before significant capital is at risk.
