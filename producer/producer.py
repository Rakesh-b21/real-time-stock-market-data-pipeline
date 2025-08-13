import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv
import yfinance as yf
from confluent_kafka import Producer
import pandas as pd
import sys
import traceback

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.company_manager import company_manager

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedStockProducer:    
    def __init__(self):
        self.kafka_config = {
            'bootstrap.servers': os.getenv('KAFKA_BROKER', 'localhost:9092'),
            'client.id': 'enhanced-stock-producer'
        }
        self.topic = os.getenv('KAFKA_TOPIC', 'stock_market_data')
        self.tickers = self._load_tickers()
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '10'))
        self.max_cycles = int(os.getenv('MAX_CYCLES', '0'))  # 0 means run forever
        
        # Initialize Kafka producer
        self.producer = Producer(self.kafka_config)
        
        # Initialize company manager
        self.company_manager = company_manager
        
        # Initialize in-memory cache for latest trade dates
        self.latest_trade_dates = {}
        
        # Pre-create companies for all tickers and load initial trade dates
        self._initialize_companies()
        self._load_initial_trade_dates()
    
    def _load_tickers(self) -> List[str]:
        """Load ticker symbols from configuration"""
        # Default tickers if not specified
        default_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC', 'UBER', 'PLTR', 'JPM', 'MS', 'WMT', 'JNJ', 'KO']
        #default_tickers = ['RELIANCE.NS','TCS.NS','HDFCBANK.NS','INFY.NS','ICICIBANK.NS','SBIN.NS','HINDUNILVR.NS','BAJFINANCE.NS','ADANIENT.NS','TATAMOTORS.NS']
        
        # Try to load from environment variable
        tickers_env = os.getenv('TICKERS')
        if tickers_env:
            return [ticker.strip() for ticker in tickers_env.split(',')]
        
        return default_tickers
    
    def _initialize_companies(self):
        """Initialize companies in the database for all tickers"""
        logger.info("Initializing companies in database...")
        results = self.company_manager.bulk_create_companies(self.tickers)
        
        successful = sum(1 for result in results.values() if result is not None)
        failed = len(results) - successful
        
        logger.info(f"Company initialization complete: {successful} successful, {failed} failed")
        
        if failed > 0:
            failed_tickers = [ticker for ticker, result in results.items() if result is None]
            logger.warning(f"Failed to initialize companies for: {failed_tickers}")
    
    def _fetch_stock_data(self, ticker: str) -> Optional[Dict]:
        """Fetch stock data from Yahoo Finance"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get current market data
            current_data = stock.history(period='1d', interval='1m')
            
            if current_data.empty:
                logger.warning(f"No data available for {ticker}")
                return None
            
            # Get the latest data point
            latest = current_data.iloc[-1]
            
            # Get company info
            company_info = self.company_manager.get_company_by_ticker(ticker)
            if not company_info:
                logger.warning(f"Company info not found for {ticker}")
                return None
            
            # Prepare data structure
            data = {
                'company_id': company_info['company_id'],
                'ticker_symbol': ticker,
                'company_name': company_info['company_name'],
                'industry': company_info['industry_name'],
                'sector': company_info['sector'],
                'exchange': company_info['exchange'],
                'currency': company_info['currency'],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'trade_datetime': latest.name.isoformat(),
                'current_price': float(latest['Close']),
                'open_price': float(latest['Open']),
                'high_price': float(latest['High']),
                'low_price': float(latest['Low']),
                'volume': int(latest['Volume']),
                'adjusted_close': float(latest['Close']),  # For historical data
                # Additional market data
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'price_to_book': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'beta': info.get('beta'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
                'avg_volume': info.get('averageVolume'),
                'shares_outstanding': info.get('sharesOutstanding')
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            self._log_error('producer', ticker, 'data_fetch_error', str(e), {'ticker': ticker})
            return None
    
    def _serialize_for_json(self, obj):
        """Custom JSON serializer that handles UUID and other non-serializable objects"""
        import uuid
        from datetime import datetime, date
        
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return str(obj)
    
    def _log_error(self, component: str, ticker: str, error_type: str, message: str, context: Dict = None):
        """Log error to database"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                company_info = self.company_manager.get_company_by_ticker(ticker)
                company_id = company_info['company_id'] if company_info else None
                
                # Safely serialize context with UUID handling
                safe_context = {}
                if context:
                    for key, value in context.items():
                        try:
                            # Test if value is JSON serializable
                            json.dumps(value)
                            safe_context[key] = value
                        except (TypeError, ValueError):
                            # Use custom serializer for non-serializable objects
                            safe_context[key] = self._serialize_for_json(value)
                
                cur.execute("""
                    INSERT INTO ingestion_errors (
                        component_name, company_id, error_type, error_message, 
                        error_details, data_context
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    component, company_id, error_type, message,
                    json.dumps({'traceback': traceback.format_exc()}), 
                    json.dumps(safe_context)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
        finally:
            if 'conn' in locals():
                # Return connection to pool instead of closing
                try:
                    from shared.database import db_manager
                    db_manager.put_connection(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    conn.close()
    
    def _delivery_report(self, err, msg):
        """Callback for Kafka message delivery"""
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')
    
    def _produce_message(self, data: Dict):
        """Produce message to Kafka topic"""
        try:
            # Serialize data to JSON
            message = json.dumps(data, default=str)
            
            # Produce message
            self.producer.produce(
                topic=self.topic,
                key=data['ticker_symbol'].encode('utf-8'),
                value=message.encode('utf-8'),
                callback=self._delivery_report
            )
            
            logger.info(f"Produced message for {data['ticker_symbol']}: {data['currency']} {data['current_price']:.2f}")
            
        except Exception as e:
            logger.error(f"Error producing message for {data['ticker_symbol']}: {e}")
            self._log_error('producer', data['ticker_symbol'], 'kafka_produce_error', str(e), data)
    
    def _load_initial_trade_dates(self):
        """Load initial trade dates for all companies from the database"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT company_id, MAX(trade_datetime) as latest_date
                    FROM stock_prices_realtime
                    GROUP BY company_id
                """)
                for company_id, latest_datetime in cur.fetchall():
                    if latest_datetime:
                        self.latest_trade_dates[company_id] = latest_datetime
                logger.info(f"Loaded initial trade dates for {len(self.latest_trade_dates)} companies")
        except Exception as e:
            logger.error(f"Error loading initial trade dates: {e}")
            raise
    
    def _store_realtime_data(self, data: Dict):
        """Store real-time data - only insert if trade date has changed for company"""
        try:
            conn = self.company_manager.get_db_connection()
            trade_datetime = datetime.fromisoformat(data['trade_datetime'].replace('Z', '+00:00'))
            trade_date = trade_datetime.date()
            company_id = data['company_id']
            
            # Check cache first to avoid DB query
            last_trade_datetime = self.latest_trade_dates.get(company_id)
            
            # If we have a cached datetime and it matches the current trade datetime, skip insert
            if last_trade_datetime and last_trade_datetime == trade_datetime:
                logger.debug(f"Skipping duplicate trade datetime {trade_datetime} for company_id {company_id}")
                return
            
            # Validate required fields before insert (prevent null constraint violations)
            required_fields = ['current_price', 'open_price', 'high_price', 'low_price', 'volume']
            missing_fields = []
            null_fields = []
            
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
                elif data[field] is None:
                    null_fields.append(field)
                elif isinstance(data[field], (int, float)):
                    # Special handling for volume: allow 0 (legitimate for NSE stocks), reject negative and NaN
                    if field == 'volume':
                        if data[field] < 0 or data[field] != data[field]:  # Reject negative or NaN
                            null_fields.append(f"{field} (invalid value: {data[field]})")
                    else:
                        # For price fields: reject <= 0 or NaN
                        if data[field] <= 0 or data[field] != data[field]:
                            null_fields.append(f"{field} (invalid value: {data[field]})")
            
            if missing_fields or null_fields:
                error_msg = f"Invalid data for {data['ticker_symbol']}: "
                if missing_fields:
                    error_msg += f"missing fields: {missing_fields}, "
                if null_fields:
                    error_msg += f"null/invalid fields: {null_fields}"
                logger.warning(error_msg)
                return  # Skip this record
            
            with conn.cursor() as cur:
                # Use INSERT ... ON CONFLICT or simple INSERT based on cache logic
                # Since we already check cache above, we can use simple INSERT
                # Double-check data validity before SQL execution (defensive programming)
                values_to_insert = (
                    company_id, trade_datetime, data['current_price'], data['volume'],
                    data['open_price'], data['high_price'], data['low_price']
                )
                
                # Verify no None values in the tuple
                if any(v is None for v in values_to_insert):
                    logger.error(f"Attempted to insert None values for {data['ticker_symbol']}: {values_to_insert}")
                    return
                
                cur.execute("""
                    INSERT INTO stock_prices_realtime (
                        company_id, trade_datetime, current_price, volume, 
                        open_price, high_price, low_price
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, values_to_insert)
                
                conn.commit()
                
                # Only update cache and log success AFTER successful commit
                self.latest_trade_dates[company_id] = trade_datetime
                logger.info(f"Successfully stored real-time data for {data['ticker_symbol']} at {trade_datetime}")
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing real-time data for {data['ticker_symbol']}: {e}")
            self._log_error('producer', data['ticker_symbol'], 'db_error', str(e), data)
            # Invalidate cache on error to force reload on next attempt
            if company_id in self.latest_trade_dates:
                del self.latest_trade_dates[company_id]
            raise
        finally:
            if 'conn' in locals():
                # Return connection to pool instead of closing
                try:
                    from shared.database import db_manager
                    db_manager.put_connection(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    conn.close()
    
    def _migrate_realtime_to_historical(self):
        """Migrate latest real-time data per date to historical table"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                # Call the database function to migrate data
                cur.execute("SELECT migrate_realtime_to_historical()")
                migrated_count = cur.fetchone()[0]
                
                if migrated_count > 0:
                    logger.info(f"Migrated {migrated_count} records from real-time to historical")
                
                conn.commit()
                return migrated_count
                
        except Exception as e:
            logger.error(f"Error migrating real-time to historical data: {e}")
            if 'conn' in locals():
                conn.rollback()
            return 0
        finally:
            if 'conn' in locals():
                # Return connection to pool instead of closing
                try:
                    from shared.database import db_manager
                    db_manager.put_connection(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    conn.close()
    

    
    def _store_historical_data(self, data: Dict):
        """Store historical data with SCD Type 2 tracking - only once per day"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                trade_date = datetime.fromisoformat(data['trade_datetime'].replace('Z', '+00:00')).date()
                
                # Check if we already have data for this date
                cur.execute("""
                    SELECT price_id, close_price, adjusted_close_price
                    FROM stock_prices_historical 
                    WHERE company_id = %s AND trade_date = %s AND is_current = TRUE
                """, (data['company_id'], trade_date))
                
                existing = cur.fetchone()
                
                if existing:
                    # Skip if we already have data for this date (avoid duplicates)
                    logger.debug(f"Historical data already exists for {data['ticker_symbol']} on {trade_date}")
                    return
                else:
                    # Insert new record only if we don't have data for this date
                    cur.execute("""
                        INSERT INTO stock_prices_historical (
                            company_id, trade_date, open_price, high_price, low_price,
                            close_price, adjusted_close_price, volume, start_date, is_current
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    """, (
                        data['company_id'], trade_date,
                        data['open_price'], data['high_price'], data['low_price'],
                        data['current_price'], data['adjusted_close'], data['volume'],
                        trade_date
                    ))
                    logger.info(f"Inserted new historical data for {data['ticker_symbol']} on {trade_date}")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing historical data for {data['ticker_symbol']}: {e}")
            self._log_error('producer', data['ticker_symbol'], 'historical_store_error', str(e), data)
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
                # Return connection to pool instead of closing
                try:
                    from shared.database import db_manager
                    db_manager.put_connection(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    conn.close()
    
    def run(self):
        """Main producer loop"""
        logger.info(f"Starting Enhanced Stock Producer with {len(self.tickers)} tickers")
        logger.info(f"Tickers: {', '.join(self.tickers)}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Max cycles: {self.max_cycles if self.max_cycles > 0 else 'unlimited'}")
        
        cycles = 0
        
        try:
            while True:
                cycle_start = time.time()
                logger.info(f"Starting cycle {cycles + 1}")
                
                for ticker in self.tickers:
                    try:
                        # Fetch stock data
                        data = self._fetch_stock_data(ticker)
                        
                        if data:
                            # Store real-time data (enhanced with smart insert logic)
                            self._store_realtime_data(data)
                            
                            # Store historical data (original approach)
                            self._store_historical_data(data)
                            
                            # Produce to Kafka for real-time analytics
                            self._produce_message(data)
                        
                    except Exception as e:
                        logger.error(f"Error processing {ticker}: {e}")
                        self._log_error('producer', ticker, 'processing_error', str(e))
                
                # Flush Kafka producer
                self.producer.flush()
                
                cycles += 1
                
                # Check if we should stop
                if self.max_cycles > 0 and cycles >= self.max_cycles:
                    logger.info(f"Reached maximum cycles ({self.max_cycles}). Stopping producer.")
                    break
                
                # Calculate sleep time
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.poll_interval - cycle_duration)
                
                if sleep_time > 0:
                    logger.info(f"Cycle {cycles} completed in {cycle_duration:.2f}s. Sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Cycle {cycles} took {cycle_duration:.2f}s, longer than poll interval ({self.poll_interval}s)")
        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Shutting down producer...")
        except Exception as e:
            logger.error(f"Unexpected error in producer: {e}")
            raise
        finally:
            self.producer.flush()
            logger.info("Enhanced Stock Producer stopped")

def main():
    """Main entry point"""
    producer = EnhancedStockProducer()
    producer.run()

if __name__ == "__main__":
    main() 