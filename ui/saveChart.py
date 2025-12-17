
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import pytz # Import pytz
import plotly.graph_objects as go


def convertTimeStampToTimeZoneAware(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts a DataFrame with a 'ts' column (in milliseconds) to one with a 
    Timezone-Aware (Asia/Kolkata) DatetimeIndex.
    """
    df = df.copy() # Work on a copy
    
    # Check if 'ts' column exists (it should, as the caller should pass the raw DF)
    if 'ts' not in df.columns:
        print("Error: 'ts' column not found in DataFrame for conversion.")
        return df

    # 1. Convert 'ts' (milliseconds) to naive datetime
    df['Date'] = pd.to_datetime(df['ts'], unit='ms')
    
    # 2. Localize to UTC (assuming the long integer timestamp represents UTC)
    # This is a common practice for Unix-like timestamps.
    df['Date'] = df['Date'].dt.tz_localize('UTC')
    
    # 3. Convert to 'Asia/Kolkata' timezone
    df['Date'] = df['Date'].dt.tz_convert('Asia/Kolkata')
    
    # 4. Set the new timezone-aware 'Date' column as the index
    df.set_index('Date', inplace=True)
    df.index.name = "Date"
    
    # 5. Drop the old 'ts' column
    df.drop(columns=['ts'], inplace=True, errors='ignore')
    
    return df
 
def plotMe(symbol:str, my_ohlc_df_raw, trades_list) :
    # Work on a copy of the raw DataFrame
    my_ohlc_df = my_ohlc_df_raw.copy() 
    
    # 1. Convert the 'ts' (ms) column into a timezone-aware DatetimeIndex (Asia/Kolkata)
    my_ohlc_df = convertTimeStampToTimeZoneAware(my_ohlc_df)

    
    # 2. Rename columns to match conventions
    my_ohlc_df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 
                            'close': 'Close', 'volume': 'Volume'}, inplace=True)

    # 3. Ensure the index is sorted
    my_ohlc_df.sort_index(inplace=True)

    print(my_ohlc_df.tail())
    
    trade_data_dicts =[]
    trades_annotations = []
    
    if trades_list :
        for trade in trades_list:
            pnl =  trade.exit_price-trade.entry_price if trade.side=="LONG" else trade.entry_price -trade.exit_price
            
            # trade.entry_ts and trade.exit_ts are expected to be long integers (milliseconds)
            trade_data_dicts.append({
                'entry_ts': trade.entry_ts, 'entry_price': trade.entry_price, 'side': trade.side,
                'exit_ts': trade.exit_ts, 'exit_price': trade.exit_price, 'pnl': pnl
            })
        
        signals_df = pd.DataFrame(trade_data_dicts)
        
        # --- Trade Timestamp Conversion and Index Search ---
        for index, trade in signals_df.iterrows():
            
            # Convert entry_ts (ms) to a timezone-aware datetime object for correct comparison
            # 1. Convert ms timestamp to naive datetime
            entry_ts_naive = pd.to_datetime(trade['entry_ts'], unit='ms')
            # 2. Localize to UTC (consistent with OHLC data creation)
            entry_ts_aware = entry_ts_naive.tz_localize('UTC') 

            # Convert exit_ts (ms) to a timezone-aware datetime object
            exit_ts_naive = pd.to_datetime(trade['exit_ts'], unit='ms')
            exit_ts_aware = exit_ts_naive.tz_localize('UTC')

            # The OHLC index is timezone-aware ('Asia/Kolkata'). 
            # searchsorted requires a timezone-aware object for comparison.
            # CRITICAL FIX: The OHLC index is created by localizing to UTC *then* converting to Asia/Kolkata.
            # To correctly search this index, we must use a timestamp that has the *same UTC equivalent*. 
            # Simply using the UTC-localized time allows pandas to perform the correct search.
            
            entry_idx = my_ohlc_df.index.searchsorted(entry_ts_aware.tz_convert('Asia/Kolkata'))
            exit_idx = my_ohlc_df.index.searchsorted(exit_ts_aware.tz_convert('Asia/Kolkata'))
            
            row_count = my_ohlc_df.shape[0]
            
            # Boundary checks
            if entry_idx >= row_count:
                entry_idx = row_count - 1
            if exit_idx >= row_count:
                exit_idx = row_count - 1
                
            # If the index is 0 and it's before the first OHLC bar, adjust
            if entry_idx == 0 and entry_ts_aware.tz_convert('Asia/Kolkata') < my_ohlc_df.index.min():
                 print(f"Trade entry {trade['entry_ts']} is before first OHLC bar. Adjusting to index 0.")
            
            if exit_idx == 0 and exit_ts_aware.tz_convert('Asia/Kolkata') < my_ohlc_df.index.min():
                 print(f"Trade exit {trade['exit_ts']} is before first OHLC bar. Adjusting to index 0.")


            print(f" SIDE:{trade['side']}:{trade['pnl']} - Entry Index: {entry_idx}, Exit Index: {exit_idx} ")
            trades_annotations.append({
                'entry_idx': entry_idx ,'exit_idx': exit_idx, 'entry_price': trade['entry_price'], 'exit_price': trade['exit_price'],
                 'side':trade['side']
            })

    savePlotlyHTML(symbol, my_ohlc_df, trades_annotations)
 
    




# Removed create_offset_series as it's not used for Plotly




def savePlotlyHTML(symbol,my_ohlc_df,trades) :
    # my_ohlc_df is already the correctly formatted, time-zone-aware DataFrame.
    
    fig = go.Figure(data=[go.Candlestick(x=my_ohlc_df.index,
                                        open=my_ohlc_df['Open'],
                                        high=my_ohlc_df['High'],
                                        low=my_ohlc_df['Low'],
                                        close=my_ohlc_df['Close'],
                                        name='Candles')])

    # Add volume bars 
    fig.add_trace(go.Bar(x=my_ohlc_df.index, y=my_ohlc_df['Volume'], name='Volume',
                        # Color logic based on Open/Close
                        marker={'color': ['green' if o-c < 0 else 'red' for o, c in zip(my_ohlc_df['Open'], my_ohlc_df['Close'])]},
                        yaxis='y2'))

 

    # 4. Add trade annotations and markers
    for i, trade in enumerate(trades):
        # Ensure indices are within bounds before accessing
        if trade['entry_idx'] >= len(my_ohlc_df.index) or trade['exit_idx'] >= len(my_ohlc_df.index):
             print(f"Trade {i} indices out of bounds. Skipping.")
             continue
             
        pnl = round(trade['exit_price'] - trade['entry_price'] if trade['side'] == 'LONG' else trade['entry_price'] - trade['exit_price'], 2)
        color = 'green' if pnl >= 0 else 'red'
        entry_marker_symbol = 'arrow-up' if trade['side'] == 'LONG' else 'arrow-down'
        exit_marker_symbol = 'circle' 
        
        # Get the datetime index value at the calculated index
        entry_datetime = my_ohlc_df.index[trade['entry_idx']]
        exit_datetime = my_ohlc_df.index[trade['exit_idx']]
        
        # Add entry marker
        fig.add_trace(go.Scatter(
            x=[entry_datetime],
            y=[trade['entry_price']],
            mode='markers',
            marker=dict(color=color, size=12, symbol=entry_marker_symbol),
            name=f"ID=[{i+1}]({trade['side']})",
            showlegend=False
        ))
        
        # Add exit marker and P&L annotation
        fig.add_trace(go.Scatter(
            x=[exit_datetime],
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
            x=[entry_datetime, exit_datetime],
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
    print(f"Chart saved successfully as '{save_filename}'")