import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from dotenv import load_dotenv
from shared.config import ml_config
from shared.database import db_manager

load_dotenv()

MODEL_PATH = ml_config.config['model_path']
WINDOW_SIZE = ml_config.config['window_size']


def get_db_connection():
    return db_manager.get_connection()

def fetch_latest_data(ticker_symbol='AAPL', limit=100):
    conn = get_db_connection()
    query = """
        SELECT spr.trade_datetime as timestamp, spr.current_price, c.company_id
        FROM stock_prices_realtime spr
        JOIN companies c ON spr.company_id = c.company_id
        WHERE c.ticker_symbol = %s
        ORDER BY spr.trade_datetime ASC
        LIMIT %s
    """
    df = pd.read_sql_query(query, conn, params=[ticker_symbol, limit])
    if conn:
        db_manager.put_connection(conn)
    return df

def create_features(df, window=WINDOW_SIZE):
    X, timestamps = [], []
    prices = df['current_price'].values
    ts = df['timestamp'].values
    for i in range(window, len(prices)):
        X.append(prices[i-window:i])
        timestamps.append(ts[i])
    return np.array(X), timestamps

def insert_predictions(company_id, ticker_symbol, timestamps, preds, model_type='LinearRegression'):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get the latest model_id for this model type
    cur.execute("""
        SELECT model_id FROM ml_models 
        WHERE model_type = %s 
        ORDER BY created_at DESC 
        LIMIT 1
    """, (model_type,))
    result = cur.fetchone()
    model_id = result[0] if result else None
    
    for ts, pred in zip(timestamps, preds):
        # Convert numpy.datetime64 to Python datetime
        if isinstance(ts, np.datetime64):
            ts = pd.to_datetime(ts).to_pydatetime()
        
        # Calculate prediction date (next day)
        predicted_date = ts + pd.Timedelta(days=1)
        
        cur.execute("""
            INSERT INTO predictions (
                company_id, model_id, timestamp, predicted_date, predicted_price, 
                prediction_type, confidence_score, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (company_id, model_id, predicted_date) DO UPDATE SET
                predicted_price = EXCLUDED.predicted_price,
                confidence_score = EXCLUDED.confidence_score,
                updated_at = CURRENT_TIMESTAMP;
        """, (company_id, model_id, ts, predicted_date, float(pred), 'next_price', 0.8))
    
    conn.commit()
    cur.close()
    if conn:
        db_manager.put_connection(conn)

def main():
    ticker_symbol = os.getenv('PREDICT_SYMBOL', 'AAPL')
    print(f"Running batch prediction for ticker symbol: {ticker_symbol}")
    
    df = fetch_latest_data(ticker_symbol, 100)
    if len(df) < WINDOW_SIZE:
        print("Not enough data for prediction.")
        return
    
    if df.empty:
        print(f"No data found for ticker symbol: {ticker_symbol}")
        return
    
    company_id = df['company_id'].iloc[0]
    X, timestamps = create_features(df)
    
    try:
        model = joblib.load(MODEL_PATH)
        preds = model.predict(X)
        insert_predictions(company_id, ticker_symbol, timestamps, preds)
        print(f"Inserted {len(preds)} predictions for {ticker_symbol}.")
    except FileNotFoundError:
        print(f"Model file not found at {MODEL_PATH}. Please train the model first.")
    except Exception as e:
        print(f"Error during prediction: {e}")

if __name__ == "__main__":
    main() 