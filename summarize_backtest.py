from pymongo import MongoClient
import pandas as pd

def summarize_results():
    client = MongoClient("mongodb://localhost:27017")
    db = client["auction_trading"]
    trades_collection = db["closed_trades"]
    
    trades = list(trades_collection.find({}, {"_id": 0}))
    
    if not trades:
        print("No trades found in DB.")
        return

    df = pd.DataFrame(trades)
    
    # Calculate PnL if not present (logic from main.py)
    # pnl = exit - entry (Long), entry - exit (Short)
    if "pnl" not in df.columns:
        df["pnl"] = df.apply(lambda row: (row["exit_price"] - row["entry_price"]) if row["side"] == "LONG" else (row["entry_price"] - row["exit_price"]), axis=1)
    
    total_trades = len(df)
    total_pnl = df["pnl"].sum()
    win_trades = df[df["pnl"] > 0]
    loss_trades = df[df["pnl"] <= 0]
    win_rate = (len(win_trades) / total_trades) * 100 if total_trades > 0 else 0
    
    print("=" * 40)
    print("      BACKTEST RESULTS SUMMARY      ")
    print("=" * 40)
    print(f"Total Trades: {total_trades}")
    print(f"Total PnL   : {total_pnl:.2f}")
    print(f"Win Rate    : {win_rate:.1f}%")
    print("-" * 40)
    print("By Side:")
    print(df.groupby("side")[["pnl"]].agg(["count", "sum", "mean"]))
    print("-" * 40)
    print("Detailed Trades:")
    print(df[["symbol", "side", "entry_price", "exit_price", "pnl", "reason"]].to_string())

if __name__ == "__main__":
    summarize_results()
