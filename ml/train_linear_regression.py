import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
from dotenv import load_dotenv
from shared.config import ml_config
from shared.database import db_manager

load_dotenv()

MODEL_PATH = ml_config.config['model_path']
WINDOW_SIZE = ml_config.config['window_size']  # Number of previous prices to use as features


def get_db_connection():
    return db_manager.get_connection()

def fetch_data(ticker_symbol='AAPL', limit=1000):
    conn = get_db_connection()
    query = """
        SELECT spr.trade_datetime as timestamp, spr.current_price
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
    X, y = [], []
    prices = df['current_price'].values
    for i in range(window, len(prices) - 1):
        X.append(prices[i-window:i])
        y.append(prices[i+1])  # Predict next price
    return np.array(X), np.array(y)

def main():
    ticker_symbol = os.getenv('PREDICT_SYMBOL', 'AAPL')
    print(f"Fetching data for ticker symbol: {ticker_symbol}")
    df = fetch_data(ticker_symbol)
    if len(df) < WINDOW_SIZE + 2:
        print("Not enough data to train model.")
        return
    X, y = create_features(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"Test MSE: {mse:.4f}")
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    main() 