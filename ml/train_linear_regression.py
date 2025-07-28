import os
import pandas as pd
import numpy as np
import psycopg2
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
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

WINDOW_SIZE = 5  # Number of previous prices to use as features


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def fetch_data(symbol='AAPL', limit=1000):
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
    X, y = [], []
    prices = df['current_price'].values
    for i in range(window, len(prices) - 1):
        X.append(prices[i-window:i])
        y.append(prices[i+1])  # Predict next price
    return np.array(X), np.array(y)

def main():
    symbol = os.getenv('PREDICT_SYMBOL', 'AAPL')
    print(f"Fetching data for symbol: {symbol}")
    df = fetch_data(symbol)
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