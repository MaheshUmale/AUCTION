from datetime import datetime
from trading_core.persistence import QuestDBPersistence
import logging

logger = logging.getLogger(__name__)

def save_feed_data(persistence: QuestDBPersistence, symbol: str, feed: dict):
    """
    Parses and saves raw feed data to QuestDB.
    This function is designed to be called from the data ingestion service.
    """
    now = datetime.now()
    full_feed = feed.get("fullFeed", {})
    market = full_feed.get("marketFF") or full_feed.get("indexFF")

    if not market:
        return

    # Process Tick and associated data
    ltpc = market.get('ltpc')
    if ltpc and 'ltp' in ltpc and 'ltt' in ltpc:
        record = {
            'timestamp': int(ltpc['ltt']) * 1_000_000,
            'instrument_key': symbol,
            'feed_type': 'TICK',
            'insertion_time': int(ltpc['ltt']),
            'processed_time': now,
            'ltp': ltpc.get('ltp'),
            'ltq': ltpc.get('ltq'),
            'cp': market.get('cp'),
            'oi': market.get('oi'),
            'atp': market.get('atp'),
            'vtt': market.get('vtt'),
            'tbq': market.get('tbq'),
            'tsq': market.get('tsq'),
        }

        market_level = market.get('marketLevel', {})
        quotes = market_level.get('bidAskQuote', [])
        if quotes:
            record['bid_price_1'] = quotes[0].get('bidP')
            record['bid_qty_1'] = quotes[0].get('bidQ')
            record['ask_price_1'] = quotes[0].get('askP')
            record['ask_qty_1'] = quotes[0].get('askQ')

        option_greeks = full_feed.get('optionGreeks')
        if option_greeks:
            record.update({
                'delta': option_greeks.get('delta'),
                'theta': option_greeks.get('theta'),
                'gamma': option_greeks.get('gamma'),
                'vega': option_greeks.get('vega'),
                'rho': option_greeks.get('rho'),
                'iv': option_greeks.get('iv'),
            })

        try:
            persistence.save_market_data(record)
        except Exception as e:
            logger.error(f"Error saving tick data: {e}")

    # Process Candle Data
    ohlc_list = market.get("marketOHLC", {}).get("ohlc", [])
    for ohlc in ohlc_list:
        if "interval" in ohlc:
            candle_record = {
                'timestamp': int(ohlc['ts']) * 1_000_000,
                'instrument_key': symbol,
                'feed_type': f'CANDLE_{ohlc["interval"]}',
                'insertion_time': int(ohlc['ts']),
                'processed_time': now,
                'open': ohlc.get('open'),
                'high': ohlc.get('high'),
                'low': ohlc.get('low'),
                'close': ohlc.get('close'),
                'vtt': ohlc.get('vol')
            }
            try:
                persistence.save_market_data(candle_record)
            except Exception as e:
                logger.error(f"Error saving candle data: {e}")
