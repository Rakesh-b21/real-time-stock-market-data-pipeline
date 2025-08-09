"""
Enhanced Producer for Real-time Stock Market Data Pipeline
Works with the new enhanced database schema
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv
import yfinance as yf
from confluent_kafka import Producer
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
    """Enhanced producer for stock market data with company management"""
    
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
        
        # Pre-create companies for all tickers
        self._initialize_companies()
    
    def _load_tickers(self) -> List[str]:
        """Load ticker symbols from configuration"""
        # Default tickers if not specified
        default_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC']
        
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
    
    def _log_error(self, component: str, ticker: str, error_type: str, message: str, context: Dict = None):
        """Log error to database"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                company_info = self.company_manager.get_company_by_ticker(ticker)
                company_id = company_info['company_id'] if company_info else None
                
                cur.execute("""
                    INSERT INTO ingestion_errors (
                        component_name, company_id, error_type, error_message, 
                        error_details, data_context
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    component, company_id, error_type, message,
                    json.dumps({'traceback': traceback.format_exc()}), 
                    json.dumps(context or {})
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
        finally:
            if 'conn' in locals():
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
            
            logger.info(f"Produced message for {data['ticker_symbol']}: ${data['current_price']:.2f}")
            
        except Exception as e:
            logger.error(f"Error producing message for {data['ticker_symbol']}: {e}")
            self._log_error('producer', data['ticker_symbol'], 'kafka_produce_error', str(e), data)
    
    def _store_realtime_data(self, data: Dict):
        """Store real-time data directly in database"""
        try:
            conn = self.company_manager.get_db_connection()
            with conn.cursor() as cur:
                # Upsert real-time data
                cur.execute("""
                    INSERT INTO stock_prices_realtime (
                        company_id, trade_datetime, open_price, high_price, 
                        low_price, current_price, volume
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_id) DO UPDATE SET
                        trade_datetime = EXCLUDED.trade_datetime,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        current_price = EXCLUDED.current_price,
                        volume = EXCLUDED.volume,
                        last_updated = CURRENT_TIMESTAMP
                """, (
                    data['company_id'],
                    data['trade_datetime'],
                    data['open_price'],
                    data['high_price'],
                    data['low_price'],
                    data['current_price'],
                    data['volume']
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing real-time data for {data['ticker_symbol']}: {e}")
            self._log_error('producer', data['ticker_symbol'], 'database_store_error', str(e), data)
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
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
                            # Store real-time data
                            self._store_realtime_data(data)
                            
                            # Store historical data
                            self._store_historical_data(data)
                            
                            # Produce to Kafka
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