import os
import time
import json
import logging
from datetime import datetime
from confluent_kafka import Producer
import yfinance as yf
from producer.config import KAFKA_BROKER, KAFKA_TOPIC, TICKERS, POLL_INTERVAL
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

MAX_CYCLES = int(os.getenv('MAX_CYCLES', '0'))  # 0 means run forever

def fetch_stock_data(ticker):
    try:
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period='1d', interval='1m')
        if data.empty:
            return None
        latest = data.iloc[-1]
        return {
            'symbol': ticker,
            'current_price': float(latest['Close']),
            'open_price': float(latest['Open']),
            'high_price': float(latest['High']),
            'low_price': float(latest['Low']),
            'volume': int(latest['Volume']),
            'timestamp': latest.name.to_pydatetime().isoformat()
        }
    except Exception as e:
        logging.error(f"Error fetching data for {ticker}: {e}")
        return None

def delivery_report(err, msg):
    if err is not None:
        logging.error(f"Delivery failed for record {msg.key()}: {err}")
    else:
        logging.info(f"Record produced to {msg.topic()} partition [{msg.partition()}] @ offset {msg.offset()}")

def main():
    producer = Producer({'bootstrap.servers': KAFKA_BROKER})
    cycles = 0
    while True:
        for ticker in TICKERS:
            stock_data = fetch_stock_data(ticker)
            if stock_data:
                producer.produce(
                    KAFKA_TOPIC,
                    key=stock_data['symbol'],
                    value=json.dumps(stock_data),
                    callback=delivery_report
                )
        producer.flush()
        cycles += 1
        if MAX_CYCLES and cycles >= MAX_CYCLES:
            break
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main() 