import os
import time
import logging
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union
from contextlib import contextmanager

import psycopg2
import pandas as pd
from psycopg2 import pool
from psycopg2.extras import DictCursor, execute_values

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global connection pool variables
_GLOBAL_POOL_LOCK = Lock()
_GLOBAL_POOL: Optional[pool.ThreadedConnectionPool] = None

def get_global_pool() -> pool.ThreadedConnectionPool:
    """
    Get or create the global thread-safe connection pool (singleton).
    Uses a double-checked locking pattern for thread safety.
    """
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        with _GLOBAL_POOL_LOCK:
            if _GLOBAL_POOL is None:
                logger.info("Initializing global connection pool...")
                min_conn = int(os.getenv('DB_MIN_CONNECTIONS', '5'))
                max_conn = int(os.getenv('DB_MAX_CONNECTIONS', '20'))
                
                dsn = os.getenv('POSTGRES_DSN')
                if dsn:
                    pool_config = {'dsn': dsn}
                else:
                    pool_config = {
                        'host': os.getenv('POSTGRES_HOST', 'localhost'),
                        'port': os.getenv('POSTGRES_PORT', '5432'),
                        'dbname': os.getenv('POSTGRES_DB', 'stocks'),
                        'user': os.getenv('POSTGRES_USER', 'postgres'),
                        'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
                        'keepalives': 1,
                        'keepalives_idle': 30,
                        'keepalives_interval': 10,
                        'keepalives_count': 5
                    }
                
                try:
                    _GLOBAL_POOL = pool.ThreadedConnectionPool(min_conn, max_conn, **pool_config)
                    logger.info(f"Global connection pool initialized (min: {min_conn}, max: {max_conn})")
                except psycopg2.OperationalError as e:
                    logger.critical(f"Failed to initialize connection pool: {e}")
                    raise
    return _GLOBAL_POOL

class DatabaseManager:
    """
    Singleton class to manage database connections and operations using the global pool.
    Provides a clean, high-level API for database interactions.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def get_connection(self, max_retries: int = 3, retry_delay: float = 0.5) -> psycopg2.extensions.connection:
        """
        Get a connection from the global pool with robust retry logic.
        """
        pool_instance = get_global_pool()
        last_error = None

        for attempt in range(max_retries):
            try:
                conn = pool_instance.getconn()
                # Validate connection
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff

                if attempt >= 1:  # Reset pool on subsequent failures
                    logger.warning("Resetting global connection pool due to persistent errors.")
                    self.close_all_connections()
                    pool_instance = get_global_pool()

        raise pool.PoolError(f"Could not get connection after {max_retries} retries. Last error: {last_error}")

    def put_connection(self, conn: psycopg2.extensions.connection):
        """
        Return a connection to the global pool, handling potential errors.
        """
        if conn is None:
            return
        
        pool_instance = get_global_pool()
        try:
            if not conn.closed:
                if conn.status != psycopg2.extensions.STATUS_READY:
                    conn.rollback()  # Rollback any uncommitted transactions
                pool_instance.putconn(conn)
        except (psycopg2.InterfaceError, pool.PoolError) as e:
            logger.warning(f"Failed to return connection to pool, discarding it: {e}")
            if not conn.closed:
                conn.close()
        except Exception as e:
            logger.error(f"Unexpected error returning connection: {e}")
            if not conn.closed:
                conn.close()

    def close_all_connections(self):
        """Close all connections in the global pool and reset it."""
        global _GLOBAL_POOL
        if _GLOBAL_POOL is not None:
            with _GLOBAL_POOL_LOCK:
                if _GLOBAL_POOL is not None:
                    _GLOBAL_POOL.closeall()
                    _GLOBAL_POOL = None
                    logger.info("Global connection pool closed and reset.")

    @contextmanager
    def get_cursor(self, dict_cursor: bool = False):
        """
        Context manager for a database cursor with automatic connection handling.
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor_factory = DictCursor if dict_cursor else None
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                yield cur, conn
            conn.commit()
        except Exception as e:
            logger.error(f"Error during database operation: {e}", exc_info=True)
            if conn and not conn.closed:
                conn.rollback()
            raise
        finally:
            if conn:
                self.put_connection(conn)

    def execute_query(self, query: str, params: Optional[tuple] = None, fetch_one: bool = False, fetch_all: bool = False, dict_cursor: bool = False) -> Optional[Any]:
        """Execute a single query with full connection and cursor management."""
        with self.get_cursor(dict_cursor=dict_cursor) as (cur, _):
            cur.execute(query, params)
            if fetch_one:
                return cur.fetchone()
            if fetch_all:
                return cur.fetchall()
        return None

    def execute_many(self, query: str, data_list: List[tuple]) -> bool:
        """Execute a query with multiple parameter sets using execute_values."""
        try:
            with self.get_cursor() as (cur, _):
                execute_values(cur, query, data_list)
            return True
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            return False

class BatchOperation:
    """Context manager for efficient batch database operations."""

    def __init__(self, db_manager: DatabaseManager, batch_size: int = 100, autocommit: bool = True):
        self.db = db_manager
        self.batch_size = batch_size
        self.autocommit = autocommit
        self.operations: List[Tuple[str, List[tuple]]] = []
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None

    def __enter__(self) -> 'BatchOperation':
        self.conn = self.db.get_connection()
        self.cursor = self.conn.cursor()
        return self

    def add_operation(self, query: str, params: Union[tuple, List[tuple]]):
        if not self.cursor:
            raise RuntimeError("Batch context not started. Use a 'with' statement.")

        params_list = [params] if isinstance(params, tuple) else params
        for op_query, op_params in self.operations:
            if op_query == query:
                op_params.extend(params_list)
                break
        else:
            self.operations.append((query, params_list))

        if sum(len(p_list) for _, p_list in self.operations) >= self.batch_size:
            self._execute_batch()

    def _execute_batch(self):
        if not self.operations or not self.cursor or not self.conn:
            return
        try:
            for query, params_list in self.operations:
                if params_list:
                    execute_values(self.cursor, query, params_list)
            if self.autocommit:
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error during batch execution: {e}")
            self.conn.rollback()
            raise
        finally:
            self.operations = []

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                logger.error(f"Exception in batch operation: {exc_val}", exc_info=True)
                if self.conn and not self.conn.closed:
                    self.conn.rollback()
            else:
                try:
                    if self.operations:
                        self._execute_batch()
                    elif not self.autocommit and self.conn:
                        self.conn.commit()
                except Exception as e:
                    logger.error(f"Failed to commit remaining batch ops: {e}")
                    if self.conn and not self.conn.closed:
                        self.conn.rollback()
                    raise
        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.db.put_connection(self.conn)

def safe_timestamp(timestamp_value: Any) -> Optional[str]:
    """Safely convert timestamp to ISO 8601 format string."""
    if timestamp_value is None:
        return None
    try:
        return pd.to_datetime(timestamp_value).isoformat()
    except (ValueError, TypeError):
        return None

class StockDataOperations:
    """Specialized operations for inserting stock data with batching support."""
    def __init__(self, manager: Optional[DatabaseManager] = None):
        self.db = manager or db_manager

    def batch_operation(self, batch_size: int = 100, autocommit: bool = True) -> BatchOperation:
        return BatchOperation(self.db, batch_size, autocommit)

    def insert_stock_data(self, data: Union[Dict, List[Dict]], batch: Optional[BatchOperation] = None):
        query = """
            INSERT INTO stock_prices_realtime (
                company_id, trade_datetime, current_price, volume,
                open_price, high_price, low_price
            ) VALUES %s;
        """
        records = data if isinstance(data, list) else [data]
        
        # Validate and filter records to prevent null constraint violations
        valid_params = []
        for r in records:
            # Check required fields
            required_fields = {
                'company_id': r.get('company_id'),
                'timestamp': r.get('timestamp'),
                'price': r.get('price'),
                'volume': r.get('volume'),
                'open': r.get('open'),
                'high': r.get('high'),
                'low': r.get('low')
            }
            
            # Validate all required fields are present and not null
            invalid_fields = []
            for field_name, field_value in required_fields.items():
                if field_value is None:
                    invalid_fields.append(field_name)
                elif field_name in ['price', 'volume', 'open', 'high', 'low']:
                    # Validate numeric fields
                    if not isinstance(field_value, (int, float)) or field_value <= 0 or field_value != field_value:  # Check for NaN
                        invalid_fields.append(f"{field_name} (invalid: {field_value})")
            
            if invalid_fields:
                logger.warning(f"Skipping record with invalid fields: {invalid_fields}")
                continue
            
            # Add valid record
            valid_params.append((
                required_fields['company_id'],
                safe_timestamp(required_fields['timestamp']),
                required_fields['price'],
                required_fields['volume'],
                required_fields['open'],
                required_fields['high'],
                required_fields['low']
            ))
        
        if not valid_params:
            logger.warning("No valid records to insert after validation")
            return
        
        if batch:
            batch.add_operation(query, valid_params)
        else:
            self.db.execute_many(query, valid_params)

    def insert_analytics_data(self, analytics_data: Dict):
        query = """
            INSERT INTO stock_analytics (
                company_id, timestamp, rsi_14, sma_20, sma_50, ema_12, ema_26,
                bb_upper, bb_middle, bb_lower, macd, macd_signal, macd_histogram, volatility
            ) VALUES %s
            ON CONFLICT (company_id, timestamp) DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14, sma_20 = EXCLUDED.sma_20, sma_50 = EXCLUDED.sma_50,
                ema_12 = EXCLUDED.ema_12, ema_26 = EXCLUDED.ema_26, bb_upper = EXCLUDED.bb_upper,
                bb_middle = EXCLUDED.bb_middle, bb_lower = EXCLUDED.bb_lower, macd = EXCLUDED.macd,
                macd_signal = EXCLUDED.macd_signal, macd_histogram = EXCLUDED.macd_histogram,
                volatility = EXCLUDED.volatility;
        """
        params = [(
            analytics_data.get('company_id'),
            safe_timestamp(analytics_data.get('timestamp')),
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
            analytics_data.get('volatility')
        )]
        self.db.execute_many(query, params)

# Global instances
db_manager = DatabaseManager()
stock_ops = StockDataOperations()

def get_db_connection(max_retries: int = 3) -> psycopg2.extensions.connection:
    """DEPRECATED: Use db_manager.get_connection() instead."""
    logger.warning("get_db_connection is deprecated. Use db_manager.get_connection() directly.")
    return db_manager.get_connection(max_retries)
