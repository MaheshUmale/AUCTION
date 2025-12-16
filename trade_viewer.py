
# =========================
# FILE: trade_viewer.py
# =========================

from flask import Flask, jsonify
import threading
import pandas as pd
import json
def start(engine):
    app = Flask(__name__)

    @app.route("/status")
    def status():
        return jsonify({
            "open_trades": engine.trade_engine.get_open_trade_count(),
            "closed_trades": len(engine.trade_engine.closed_trades),
        })
    @app.route("/details")
    def details():
        return jsonify({
            "open_trades": engine.trade_engine.open_trades,
            "closed_trades": engine.trade_engine.closed_trades,
        })

    @app.route("/")
    def index():
        json_data = ({
            "open_trades": engine.trade_engine.open_trades,
            "closed_trades": engine.trade_engine.closed_trades,
        })
        # --- 3. Execute the function and get the output ---
        html_output_string = generate_trade_html_tables(json_data)

        return html_output_string 


    def run():
        app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)

    threading.Thread(target=run, daemon=True).start()

# Function to apply header style
def highlight_header(s):
    # This applies a custom CSS style to the header row (th elements)
    # You can customize the background-color, color, font-weight, etc.
    return 'background-color: #007bff; color: white; font-weight: bold; text-align: center;'


# --- 2. Function to process data and return a combined HTML string ---
def generate_trade_html_tables(data):
    # Process closed_trades (list of dictionaries)
    if data["closed_trades"]:
        df_closed = pd.DataFrame(data["closed_trades"])
        # Convert timestamps for readability
        df_closed['entry_ts'] = pd.to_datetime(df_closed['entry_ts'], unit='ms')
        df_closed['exit_ts'] = pd.to_datetime(df_closed['exit_ts'], unit='ms')
        # Generate HTML with Bootstrap classes for styling
        
        html_closed = df_closed.to_html(index=False, classes="table table-striped table-hover", border=0)
        
        # Add Bootstrap header class (e.g., 'thead-dark' or 'thead-light') using string replace
        # Use .replace() with count=1 to only replace the first occurrence (the main thead)
        html_closed = html_closed.replace("<thead>", "<thead class='thead-dark'>", 1)

    else:
        html_closed = "<p>No closed trades to display.</p>"

    # Process open_trades (dictionary of dictionaries)
    if data["open_trades"]:
        # Use a list of values to easily create the DataFrame
        open_trades_list = list(data["open_trades"].values())
        df_open = pd.DataFrame(open_trades_list)
        # Convert timestamps for readability
        df_open['entry_ts'] = pd.to_datetime(df_open['entry_ts'], unit='ms')
        html_open = df_open.to_html(index=False, classes="table table-striped table-hover", border=0)
        html_open=  html_open.replace("<thead>", "<thead class='thead-dark'>", 1)
    else:
        html_open = "<p>No open trades to display.</p>"

    # Combine all parts into one clean HTML string
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trade Report</title>
        <!-- Optional: Add Bootstrap CSS for nice formatting -->
      <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <!-- Bootstrap CSS CDN link from jsDelivr -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
     <style>
        /* Optional: Add some padding/margin for better viewing */
        .container {{
            padding: 20px;
        }}
    </style>
</head>
    <body>
        <div class="container mt-4">
            <h1>Trade Status Overview</h1>
            <hr>
            <h2>Closed Trades</h2>
            {html_closed}
            <h2>Open Trades</h2>
            {html_open}
        </div>
    </body>
    </html>
    """
    return full_html
