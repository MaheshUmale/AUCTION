
from pymongo import MongoClient
import pandas as pd

def analyze():
    client = MongoClient("mongodb://localhost:27017")
    db = client["auction_trading"]
    col = db["closed_trades"]
    
    trades = list(col.find({}, {"_id": 0}))
    
    if not trades:
        print("No trades found in DB.")
        return

    df = pd.DataFrame(trades)
    
    # Ensure numeric pnl
    df["pnl"] = pd.to_numeric(df["pnl"])
    
    # Calculate Duration (in minutes)
    # Timestamps are likely in milliseconds? Let's check.
    # If exit_ts or entry_ts are huge, they are ms.
    if df["entry_ts"].max() > 1e11: 
        df["duration_min"] = (df["exit_ts"] - df["entry_ts"]) / 1000 / 60
    else:
        df["duration_min"] = (df["exit_ts"] - df["entry_ts"]) / 60

    print("-" * 50)
    print(f"Total Trades: {len(df)}")
    print(f"Total PnL: {df['pnl'].sum():.2f}")
    print(f"Win Rate: {(df[df['pnl'] > 0].shape[0] / len(df)) * 100:.2f}%")
    print(f"Avg PnL per Trade: {df['pnl'].mean():.2f}")
    print("-" * 50)
    
    print("\nDuration Stats (Minutes):")
    print(df["duration_min"].describe()[['mean', 'min', 'max', '50%']])

    print("\nWin/Loss Stats:")
    winners = df[df["pnl"] > 0]
    losers = df[df["pnl"] <= 0]
    
    print(f"Avg Win: {winners['pnl'].mean():.2f}")
    print(f"Max Win: {winners['pnl'].max():.2f}")
    print(f"Avg Loss: {losers['pnl'].mean():.2f}")
    print(f"Max Loss: {losers['pnl'].min():.2f}") # Max drawdown on single trade
    
    print("\nBy Symbol:")
    symbol_grp = df.groupby("symbol")["pnl"].agg(["count", "sum", "mean"])
    print(symbol_grp)
    
    print("\nBy Side:")
    side_grp = df.groupby("side")["pnl"].agg(["count", "sum", "mean"])
    print(side_grp)
    
    print("\nTop 5 Winners:")
    print(df.nlargest(5, "pnl")[["symbol", "side", "pnl", "entry_price", "exit_price"]])
    
    print("\nTop 5 Losers:")
    print(df.nsmallest(5, "pnl")[["symbol", "side", "pnl", "entry_price", "exit_price"]])

if __name__ == "__main__":
    analyze()
