import os

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'stock_market_data')
TICKERS = os.getenv('TICKERS', 'AAPL,MSFT,GOOGL,AMZN,TSLA').split(',')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))  # seconds 