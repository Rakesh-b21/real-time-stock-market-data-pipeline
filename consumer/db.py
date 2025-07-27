import os
import psycopg2
from psycopg2.extras import execute_values
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_db_connection():
    try:
        return psycopg2.connect(
            dbname=os.getenv('POSTGRES_DB', 'stocks'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise

def insert_stock_data(conn, data):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stock_prices (symbol, current_price, open_price, high_price, low_price, volume, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (
                    data['symbol'],
                    data['current_price'],
                    data.get('open_price'),
                    data.get('high_price'),
                    data.get('low_price'),
                    data.get('volume'),
                    data['timestamp']
                )
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error inserting data for {data.get('symbol', 'UNKNOWN')}: {e}")
        conn.rollback() 