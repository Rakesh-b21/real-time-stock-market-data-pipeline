import logging
from typing import Dict, Optional

# Centralized database utilities
from shared.database import db_manager, stock_ops

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def get_db_connection():
    """Backward-compatible wrapper using shared DatabaseManager.
    Prefer relying on shared.stock_ops helpers instead of direct connections.
    """
    return db_manager.get_connection()


def insert_stock_data(conn, data: Dict) -> None:
    """Insert stock data using centralized shared logic.
    The `conn` parameter is ignored for centralized handling but kept for backward compatibility.
    """
    try:
        success = stock_ops.insert_stock_data(data)
        if not success:
            raise RuntimeError("Insert failed after retries")
    except Exception as e:
        logging.error(f"Error inserting data for {data.get('ticker_symbol', 'UNKNOWN')}: {e}")