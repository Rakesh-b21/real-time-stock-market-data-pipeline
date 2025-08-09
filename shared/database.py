"""
Shared Database Connection and Operations Module
Centralizes all database-related functionality to eliminate code duplication
"""

import os
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Centralized database connection and operations manager"""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize with optional custom config, defaults to shared.config.db_config"""
        try:
            # Prefer centralized config
            if config is not None:
                self.config = config
            else:
                from shared.config import db_config as _db_config
                self.config = _db_config.get_config()
        except Exception:
            # Fallback to envs if shared.config import path has issues
            self.config = {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': os.getenv('POSTGRES_PORT', '5432'),
                'database': os.getenv('POSTGRES_DB', 'stocks'),
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
            }
        self._connection = None
    
    def get_connection(self, max_retries: int = 3) -> psycopg2.extensions.connection:
        """Get database connection with retry logic"""
        for attempt in range(max_retries):
            try:
                # Optional debugging: log masked config and drop into debugger
                if os.getenv('DEBUG_DB_CONFIG', '0') == '1':
                    safe_cfg = dict(self.config)
                    if 'password' in safe_cfg:
                        safe_cfg['password'] = '***'
                    logger.warning(f"Attempting DB connection with config (masked): {safe_cfg}")
                    if os.getenv('DEBUG_DB_BREAKPOINT', '0') == '1':
                        import pdb
                        pdb.set_trace()
                dsn = os.getenv('POSTGRES_DSN')
                if dsn:
                    if os.getenv('DEBUG_DB_CONFIG', '0') == '1':
                        logger.warning("Connecting via POSTGRES_DSN override")
                    conn = psycopg2.connect(dsn)
                else:
                    conn = psycopg2.connect(**self.config)
                conn.autocommit = False
                return conn
            except Exception as e:
                logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = False):
        """Context manager for database cursor with automatic cleanup"""
        conn = None
        try:
            conn = self.get_connection()
            cursor_factory = RealDictCursor if dict_cursor else None
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                yield cur, conn
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None, 
                     fetch_one: bool = False, fetch_all: bool = False,
                     dict_cursor: bool = False) -> Optional[Any]:
        """Execute a query with automatic connection management"""
        with self.get_cursor(dict_cursor=dict_cursor) as (cur, conn):
            cur.execute(query, params)
            
            if fetch_one:
                return cur.fetchone()
            elif fetch_all:
                return cur.fetchall()
            return None
    
    def execute_many(self, query: str, data_list: List[tuple]) -> bool:
        """Execute query with multiple parameter sets"""
        try:
            with self.get_cursor() as (cur, conn):
                execute_values(cur, query, data_list)
                return True
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            return False
    
    def insert_with_retry(self, query: str, params: tuple, max_retries: int = 3) -> bool:
        """Insert data with retry logic for handling conflicts"""
        for attempt in range(max_retries):
            try:
                with self.get_cursor() as (cur, conn):
                    cur.execute(query, params)
                    return True
            except Exception as e:
                logger.error(f"Insert attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                else:
                    logger.error(f"Failed to insert after {max_retries} attempts")
                    return False
        return False


# Global database manager instance
db_manager = DatabaseManager()


def get_db_connection(max_retries: int = 3) -> psycopg2.extensions.connection:
    """Legacy function for backward compatibility"""
    return db_manager.get_connection(max_retries)


def safe_timestamp(timestamp_value: Any) -> datetime:
    """Safely convert various timestamp formats to datetime"""
    if isinstance(timestamp_value, str):
        import pandas as pd
        return pd.Timestamp(timestamp_value).to_pydatetime()
    elif timestamp_value is None:
        return datetime.now(timezone.utc)
    elif isinstance(timestamp_value, datetime):
        return timestamp_value
    else:
        return datetime.now(timezone.utc)


class StockDataOperations:
    """Specialized operations for stock data"""
    
    def __init__(self, manager: Optional[DatabaseManager] = None):
        # Use provided manager, else fall back to the global db_manager
        self.db = manager or db_manager
    
    def insert_stock_data(self, data: Dict) -> bool:
        """Insert stock data with proper error handling"""
        query = """
            INSERT INTO stock_prices_realtime (
                company_id, trade_datetime, open_price, high_price, low_price, 
                current_price, volume, last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (company_id) DO UPDATE SET
                trade_datetime = EXCLUDED.trade_datetime,
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                current_price = EXCLUDED.current_price,
                volume = EXCLUDED.volume,
                last_updated = CURRENT_TIMESTAMP;
        """
        
        params = (
            data['company_id'],
            safe_timestamp(data.get('trade_datetime')),
            data.get('open_price'),
            data.get('high_price'),
            data.get('low_price'),
            data['current_price'],
            data.get('volume')
        )
        
        return self.db.insert_with_retry(query, params)
    
    def insert_analytics_data(self, analytics_data: Dict) -> bool:
        """Insert analytics data with proper timestamp handling"""
        query = """
            INSERT INTO stock_analytics (
                company_id, timestamp, current_price, open_price, high_price, low_price, volume,
                rsi_14, sma_20, sma_50, ema_12, ema_26,
                bb_upper, bb_middle, bb_lower,
                macd, macd_signal, macd_histogram,
                volatility, price_change_percent, volume_change_percent,
                predicted_price, prediction_confidence, model_type
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
        """
        
        params = (
            analytics_data['company_id'],
            safe_timestamp(analytics_data.get('timestamp')),
            analytics_data['current_price'],
            analytics_data.get('open_price'),
            analytics_data.get('high_price'),
            analytics_data.get('low_price'),
            analytics_data.get('volume'),
            analytics_data.get('rsi_14'),
            analytics_data.get('sma_20'),
            analytics_data.get('sma_50'),
            analytics_data.get('ema_12'),
            analytics_data.get('ema_26'),
            analytics_data.get('bb_upper'),
            analytics_data.get('bb_middle'),
            analytics_data.get('bb_lower'),
            analytics_data.get('macd'),
            analytics_data.get('macd_signal'),
            analytics_data.get('macd_histogram'),
            analytics_data.get('volatility'),
            analytics_data.get('price_change_percent'),
            analytics_data.get('volume_change_percent'),
            analytics_data.get('predicted_price'),
            analytics_data.get('prediction_confidence'),
            analytics_data.get('model_type')
        )
        
        return self.db.insert_with_retry(query, params)


# Global stock operations instance
stock_ops = StockDataOperations()
