# backtester_json.py
import argparse
import pandas as pd
import json
import gzip
from trading_core.stage8_engine import LiveAuctionEngine
from trading_core.persistence import QuestDBPersistence
from trading_core.models import Tick, Trade, Candle
import config

def run_backtest(symbol: str, file_path: str):
    """
    Runs a backtest for a given symbol from a gzipped JSON file.
    """
    print(f"Running backtest for {symbol} from {file_path}...")

    # 1. Initialize Engine and Persistence
    persistence = QuestDBPersistence(db_name="auction_trading_backtest")
    engine = LiveAuctionEngine(
        config={
            "simulation_mode": True,
            "bias_timeframe_minutes": config.BIAS_TIMEFRAME_MINUTES,
            "db_name": "auction_trading_backtest"
        },
        persistence=persistence
    )
    engine.loadFromDb()

    try:
        # 2. Load data from the gzipped JSON file
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            print(f"No data found in {file_path}.")
            return

        # 3. Simulate Live Ticks
        print(f"Simulating {len(data)} ticks...")
        for feed_data in data:
            try:
                market_ff = feed_data.get("fullFeed", {}).get("marketFF", {})
                ltpc = market_ff.get("ltpc", {})
                if ltpc and 'ltp' in ltpc and 'ltt' in ltpc:
                    tick = Tick(
                        symbol=symbol,
                        ltp=float(ltpc['ltp']),
                        ts=int(ltpc['ltt']),
                    volume=int(market_ff.get("vtt", 0)),
                        total_buy_qty=int(market_ff.get("tbq", 0)),
                        total_sell_qty=int(market_ff.get("tsq", 0))
                    )
                    market_data = {
                        "instrument_key": symbol,
                        "feed_type": "TICK",
                        "timestamp": tick.ts,
                        "ltp": tick.ltp,
                        "ltt": tick.ts,
                        "vtt": tick.volume,
                        "tbq": tick.total_buy_qty,
                        "tsq": tick.total_sell_qty,
                        "insertion_time": tick.ts,
                        "processed_time": tick.ts
                    }
                    persistence.save_market_data(market_data)
                    engine.on_tick(tick)

                ohlc_list = market_ff.get("marketOHLC", {}).get("ohlc", [])
                for ohlc in ohlc_list:
                    if ohlc.get("interval") == "I1":
                        candle = Candle(
                            symbol=symbol,
                            open=float(ohlc["open"]),
                            high=float(ohlc["high"]),
                            low=float(ohlc["low"]),
                            close=float(ohlc["close"]),
                            volume=int(ohlc.get("vol", 0)),
                            ts=int(ohlc["ts"]),
                        )

                        market_data = {
                            "instrument_key": symbol,
                            "feed_type": "CANDLE_I1",
                            "timestamp": candle.ts,
                            "open": candle.open,
                            "high": candle.high,
                            "low": candle.low,
                            "close": candle.close,
                            "vtt": candle.volume,
                            "insertion_time": candle.ts,
                            "processed_time": candle.ts
                        }
                        persistence.save_market_data(market_data)
                        engine.on_candle_close(candle)

            except (ValueError, TypeError) as e:
                print(f"Skipping tick due to data error: {e}")
                continue

        # 4. Summarize Results
        trades = engine.trade_engine.closed_trades
        if trades:
            summarize(trades)
        else:
            print("No trades were executed during the backtest.")

    finally:
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
    parser = argparse.ArgumentParser(description="Run a backtest for the trading strategy from a JSON file.")
    parser.add_argument("--symbol", type=str, required=True, help="The symbol to backtest.")
    parser.add_argument("--file-path", type=str, required=True, help="The path to the gzipped JSON data file.")
    args = parser.parse_args()

    run_backtest(args.symbol, args.file_path)

if __name__ == "__main__":
    main()
