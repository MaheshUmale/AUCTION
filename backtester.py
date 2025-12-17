# backtester.py
import argparse
import pandas as pd
from datetime import datetime
from trading_core.stage8_engine import LiveAuctionEngine, LiveMarketRouter
from trading_core.persistence import QuestDBPersistence
from trading_core.models import Tick, Trade
import config

def run_backtest(symbol: str, from_date: str, to_date: str):
    """
    Runs a backtest for a given symbol and date range.
    """
    print(f"Running backtest for {symbol} from {from_date} to {to_date}...")

    # 1. Initialize Engine and Persistence
    persistence = QuestDBPersistence(db_name="auction_trading_backtest")
    engine = LiveAuctionEngine(
        simulation_mode=True,
        bias_timeframe_minutes=config.BIAS_TIMEFRAME_MINUTES,
        persistence_db_name="auction_trading_backtest"
    )
    engine.loadFromDb()
    router = LiveMarketRouter(engine)

    try:
        # 2. Fetch Historical Data from QuestDB
    ticks = persistence.fetch_tick_data(symbol, from_date, to_date)
    if not ticks:
        print(f"No data found for {symbol} in the given date range.")
        return

    # 3. Simulate Live Ticks
    print(f"Simulating {len(ticks)} ticks...")
    for tick_data in ticks:
        tick = Tick(**tick_data)
        # The router expects a message format similar to the live feed.
        message = {
            "feeds": {
                symbol: {
                    "fullFeed": {
                        "marketFF": {
                            "ltpc": {
                                "ltp": tick.ltp,
                                "ltt": tick.ts
                            },
                            "vol": tick.volume,
                            "tbq": tick.total_buy_qty,
                            "tsq": tick.total_sell_qty
                        }
                    }
                }
            }
        }
        router.on_message(message)

        # 4. Summarize and Plot Results
        trades = engine.trade_engine.closed_trades
        if trades:
            summarize(trades)
        else:
            print("No trades were executed during the backtest.")

    finally:
        router.shutdown()
        print("Backtest complete.")

def summarize(trades):
    """Summarizes the performance of a list of trades."""
    if not trades:
        print("No trades to summarize.")
        return

    df = pd.DataFrame([{
        "side": t.side,
        "pnl": t.exit_price - t.entry_price if t.side == "LONG" else t.entry_price - t.exit_price
    } for t in trades]).dropna()

    if not df.empty:
        print("\n===== Trade Summary =====")
        print(df.groupby("side")[["pnl"]].mean())
    else:
        print("No valid trades to summarize.")

def main():
    """Main function to run the backtester."""
    parser = argparse.ArgumentParser(description="Run a backtest for the trading strategy.")
    parser.add_argument("--symbol", type=str, required=True, help="The symbol to backtest.")
    parser.add_argument("--from-date", type=str, required=True, help="The start date of the backtest (YYYY-MM-DD).")
    parser.add_argument("--to-date", type=str, required=True, help="The end date of the backtest (YYYY-MM-DD).")
    args = parser.parse_args()

    run_backtest(args.symbol, args.from_date, args.to_date)

if __name__ == "__main__":
    main()
