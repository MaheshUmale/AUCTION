import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt

import plotly.graph_objects as go



def plotMe(symbol:str, my_ohlc_df, trades_list) :
 
    # 1. Convert your 'ts' column (in milliseconds) to actual datetime objects
    my_ohlc_df['Date'] = pd.to_datetime(my_ohlc_df['ts'], unit='ms')

    # 2. Set this new 'Date' column as the DataFrame index (this creates the DatetimeIndex)
    my_ohlc_df.set_index('Date', inplace=True)

    # 3. Rename columns to match mplfinance requirements (Case Sensitive)
    my_ohlc_df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 
                            'close': 'Close', 'volume': 'Volume'}, inplace=True)

    # 4. Ensure the index is sorted (required for 'method="nearest"')
    my_ohlc_df.sort_index(inplace=True)

    # 5. (Optional) Drop the old 'ts' column if you don't need it anymore
    my_ohlc_df.drop(columns=['ts'], inplace=True, errors='ignore')
    trade_data_dicts =[]
    trades_annotations = []
    side_annotations = []
    if trades_list :
        for trade in trades_list:
            pnl =  trade.exit_price-trade.entry_price if trade.side=="LONG" else trade.entry_price -trade.exit_price
            
            
            trade_data_dicts.append({
                'entry_ts': trade.entry_ts, 'entry_price': trade.entry_price, 'side': trade.side,
                'exit_ts': trade.exit_ts, 'exit_price': trade.exit_price, 'pnl': pnl
            })
        signals_df = pd.DataFrame(trade_data_dicts)
        signals_df['entry_ts'] = pd.to_datetime(signals_df['entry_ts'], unit='ms')
        signals_df['exit_ts'] = pd.to_datetime(signals_df['exit_ts'], unit='ms')

        # # --- 3. Prepare plotting data (markers) ---
        # entry_markers = [np.nan] * len(my_ohlc_df)
        # exit_markers = [np.nan] * len(my_ohlc_df)
        

        for index, trade in signals_df.iterrows():
                # This line now works because the index is a sorted DatetimeIndex:
            entry_idx = my_ohlc_df.index.searchsorted(trade['entry_ts'])
            exit_idx = my_ohlc_df.index.searchsorted(trade['exit_ts'])

            row_count = my_ohlc_df.shape[0]
            if entry_idx >= row_count:
                entry_idx =row_count-1
                
            if exit_idx >= row_count:
                exit_idx =row_count-1
                
         
            print(f" SIDE:{trade['side']}:{trade['pnl']}  ")
            trades_annotations.append({
                'entry_idx': entry_idx ,'exit_idx': exit_idx, 'entry_price': trade['entry_price'], 'exit_price': trade['exit_price'],
                 'side':trade['side']
            })




        
    # --- Calculate Dynamic Offset ---
    price_range = my_ohlc_df['High'].max() - my_ohlc_df['Low'].min()
    # Use a small fraction of the price range, e.g., 0.2%
    marker_offset = 0.002 * price_range
    text_offset = 0.005 * price_range # Slightly larger offset for the text label


    savePlotlyHTML(symbol,my_ohlc_df,trades_annotations)
 
    




def create_offset_series(markers_series, offset_val, side):
    """Applies vertical offset to a marker series."""
    offset_applied = markers_series.copy()
    if side == 'buy':
        offset_applied = offset_applied - offset_val
    elif side == 'sell':
        offset_applied = offset_applied + offset_val
    return offset_applied





def savePlotlyHTML(symbol,my_ohlc_df,trades) :
    # Assume 'my_ohlc_df', 'symbol', 'pnl_annotations' are defined from your previous code
    # my_ohlc_df must have columns 'Open', 'High', 'Low', 'Close', 'Volume' and a DateTime index


    my_ohlc_df = convertTimeStampToTimeZoneAware(my_ohlc_df)
    fig = go.Figure(data=[go.Candlestick(x=my_ohlc_df.index,
                                        open=my_ohlc_df['Open'],
                                        high=my_ohlc_df['High'],
                                        low=my_ohlc_df['Low'],
                                        close=my_ohlc_df['Close'],
                                        name='Candles')])

    # Add volume bars (Plotly handles this more automatically)
    fig.add_trace(go.Bar(x=my_ohlc_df.index, y=my_ohlc_df['Volume'], name='Volume',
                        marker={'color': ['green' if o-c < 0 else 'red' for o, c in zip(my_ohlc_df['Open'], my_ohlc_df['Close'])]},
                        yaxis='y2'))

 

        # 4. Add trade annotations and markers
    for i, trade in enumerate(trades):
        pnl = round(trade['exit_price'] - trade['entry_price'] if trade['side'] == 'LONG' else trade['entry_price'] - trade['exit_price'], 2)
        color = 'green' if pnl >= 0 else 'red'
        entry_marker_symbol = 'arrow-up' if trade['side'] == 'LONG' else 'arrow-down'
        exit_marker_symbol = 'circle' #if trade['side'] == 'LONG' else 'arrow-up'
        
        # Add entry marker
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(my_ohlc_df.index[trade['entry_idx']])],
            y=[trade['entry_price']],
            mode='markers',
            marker=dict(color=color, size=12, symbol=entry_marker_symbol),
            name=f"ID=[{i+1}]({trade['side']}",
            showlegend=False
        ))
        
        # Add exit marker and P&L annotation
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(my_ohlc_df.index[trade['exit_idx']])],
            y=[trade['exit_price']],
            mode='markers+text',
            marker=dict(color=color, size=12, symbol=exit_marker_symbol),
            text=[f"P&L: ${pnl}"],
            textposition="bottom center" if pnl >= 0 else "top center",
            name=f"{i+1} Exit",
            showlegend=False
        ))
        
        # Add a line connecting entry and exit
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(my_ohlc_df.index[trade['entry_idx']]), pd.to_datetime(my_ohlc_df.index[trade['exit_idx']])],
            y=[trade['entry_price'], trade['exit_price']],
            mode='lines',
            line=dict(color=color, width=1, dash='dash'),
            name=f"{trade['entry_price']:.2f}-{ trade['exit_price']:.2f}",
            showlegend=False
        ))

    

    fig.update_layout(
        title=f"Trades for Asset {symbol}",
        yaxis_title='Price ($)',
        xaxis_rangeslider_visible=False, # Disable the default range slider
        template='plotly_white', # Clean theme
        yaxis2={'title': 'Volume', 'overlaying': 'y', 'side': 'right'}
    )
    fig.update_layout(hovermode='x unified')

    # Export to an interactive HTML file
    save_filename = f'{symbol.replace("|","_")}_trade_visualization_interactive.html'
    fig.write_html(save_filename)
    # print(f"Chart saved successfully as '{save_filename}'")
import pandas as pd
import pytz # You might need to install this library

def convertTimeStampToTimeZoneAware(df):
    df["timestamp_ms"]=df.index
  
    columnName ="temp"

    # Assuming your data is in a DataFrame called 'df' and the column is 'timestamp_ms'
    # The unit='ms' parameter is crucial here for converting from milliseconds since epoch
    df[columnName] = pd.to_datetime(df['timestamp_ms'], unit='ms', origin='unix')

    # Localize the timezone-naive timestamps to IST (Indian Standard Time)
    # If your input milliseconds are already in IST, use tz_localize('Asia/Kolkata')
    df[columnName] = df[columnName].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata') 

    # Set the datetime column as the DataFrame index for proper plotting
    df = df.set_index(columnName)
    return df


