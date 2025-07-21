import os
import json
import logging
from confluent_kafka import Consumer, KafkaException
from consumer.db import insert_stock_data, get_db_connection
from dotenv import load_dotenv
load_dotenv()

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'stock_market_data')
KAFKA_GROUP = os.getenv('KAFKA_GROUP', 'stock_data_consumers')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '0'))  # 0 means run forever

def main():
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': KAFKA_GROUP,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False
    })
    consumer.subscribe([KAFKA_TOPIC])
    conn = get_db_connection()
    msg_count = 0
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logging.error(f"Consumer error: {msg.error()}")
                continue
            try:
                data = json.loads(msg.value().decode('utf-8'))
                insert_stock_data(conn, data)
                consumer.commit(msg)
                logging.info(f"Inserted data for {data['symbol']} at {data['timestamp']}")
                msg_count += 1
                if MAX_MESSAGES and msg_count >= MAX_MESSAGES:
                    break
            except Exception as e:
                logging.error(f"Failed to process message: {e}")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        conn.close()

if __name__ == "__main__":
    main() 