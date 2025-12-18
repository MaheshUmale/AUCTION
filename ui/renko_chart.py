from flask import Flask, render_template, request
from trading_core.persistence import QuestDBPersistence
from trading_core.models import Tick
from strategy.renko_aggregator import RenkoAggregator
import plotly.graph_objects as go
import pandas as pd

app = Flask(__name__, template_folder='templates')
persistence = QuestDBPersistence()

@app.route('/', methods=['GET', 'POST'])
def renko_chart():
    all_symbols = persistence.get_all_symbols()
    default_symbol = all_symbols[0] if all_symbols else 'default_symbol'

    symbol = request.form.get('symbol', default_symbol)
    from_date = request.form.get('from_date', '2024-01-01')
    to_date = request.form.get('to_date', '2024-01-02')

    bricks = []
    def on_renko_brick(brick):
        bricks.append(brick)

    renko_aggregator = RenkoAggregator(on_renko_brick=on_renko_brick)

    tick_data = persistence.fetch_tick_data(symbol, from_date, to_date)
    for data in tick_data:
        try:
            tick = Tick(symbol=data['symbol'], ltp=data['ltp'], ts=data['ts'])
            renko_aggregator.on_tick(tick)
        except KeyError as e:
            print(f"KeyError: {e} in tick data: {data}")


    if not bricks:
        return render_template('renko_chart.html', all_symbols=all_symbols, symbol=symbol, from_date=from_date, to_date=to_date, chart_html=None)

    df = pd.DataFrame([brick.__dict__ for brick in bricks])
    fig = go.Figure(go.Candlestick(x=df['ts'],
                                   open=df['open'],
                                   high=df['high'],
                                   low=df['low'],
                                   close=df['close']))
    chart_html = fig.to_html(full_html=False)

    return render_template('renko_chart.html', all_symbols=all_symbols, symbol=symbol, from_date=from_date, to_date=to_date, chart_html=chart_html)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
