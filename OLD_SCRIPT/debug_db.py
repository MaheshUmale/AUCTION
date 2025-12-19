
import psycopg2

def debug_db():
    conn = psycopg2.connect(
        host="localhost",
        port="8812",
        user="admin",
        password="quest",
        database="auction_trading_backtest",
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM tick_data;")
    rows = cur.fetchall()
    print(f"Verification: Found {rows[0][0]} rows in tick_data")
    cur.close()
    conn.close()

if __name__ == "__main__":
    debug_db()
