import os
import pandas as pd
import numpy as np
import psycopg2
import joblib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'stocks'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

MODEL_PATH = os.getenv('LR_MODEL_PATH', 'ml/linear_regression_model.joblib')
PREDICTIONS_TABLE = os.getenv('PREDICTIONS_TABLE', 'predictions')
WINDOW_SIZE = 5


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def fetch_latest_data(symbol='AAPL', limit=100):
    conn = get_db_connection()
    query = """
        SELECT timestamp, current_price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp ASC
        LIMIT %s
    """
    df = pd.read_sql_query(query, conn, params=[symbol, limit])
    conn.close()
    return df

def create_features(df, window=WINDOW_SIZE):
    X, timestamps = [], []
    prices = df['current_price'].values
    ts = df['timestamp'].values
    for i in range(window, len(prices)):
        X.append(prices[i-window:i])
        timestamps.append(ts[i])
    return np.array(X), timestamps

def create_predictions_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {PREDICTIONS_TABLE} (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            predicted_price DECIMAL(10, 4) NOT NULL,
            model_type VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_predictions_symbol_timestamp ON {PREDICTIONS_TABLE} (symbol, timestamp DESC);
    """)
    conn.commit()
    cur.close()
    conn.close()

def insert_predictions(symbol, timestamps, preds, model_type='LinearRegression'):
    conn = get_db_connection()
    cur = conn.cursor()
    for ts, pred in zip(timestamps, preds):
        # Convert numpy.datetime64 to Python datetime
        if isinstance(ts, np.datetime64):
            ts = pd.to_datetime(ts).to_pydatetime()
        cur.execute(f"""
            INSERT INTO {PREDICTIONS_TABLE} (symbol, timestamp, predicted_price, model_type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (symbol, ts, float(pred), model_type))
    conn.commit()
    cur.close()
    conn.close()

def main():
    symbol = os.getenv('PREDICT_SYMBOL', 'AAPL')
    print(f"Running batch prediction for symbol: {symbol}")
    create_predictions_table()
    df = fetch_latest_data(symbol, 100)
    if len(df) < WINDOW_SIZE:
        print("Not enough data for prediction.")
        return
    X, timestamps = create_features(df)
    model = joblib.load(MODEL_PATH)
    preds = model.predict(X)
    insert_predictions(symbol, timestamps, preds)
    print(f"Inserted {len(preds)} predictions into {PREDICTIONS_TABLE}.")

if __name__ == "__main__":
    main() 