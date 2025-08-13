import os
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional
from confluent_kafka import Consumer, KafkaException
import pandas as pd

from analytics.technical_indicators import TechnicalIndicators
from ml.arima_forecasting import MultiSymbolARIMAForecaster

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.company_manager import company_manager
from shared.database import db_manager
from shared.config import kafka_config, analytics_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Get message limit from environment
MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '0'))  # 0 means run forever

# Configuration for error handling
SKIP_INVALID_DATA = os.getenv('SKIP_INVALID_DATA', 'true').lower() == 'true'
SKIP_EXTREME_VALUES = os.getenv('SKIP_EXTREME_VALUES', 'true').lower() == 'true'

class AnalyticsConsumer:
    """
    Real-time analytics consumer with enhanced error handling and ARIMA forecasting
    """
    
    def __init__(self):
        # Map only the alert thresholds we need from shared analytics_config
        self.config = {
            'alert_thresholds': analytics_config.alert_thresholds
        }
        # Map shared kafka config to confluent_kafka expected keys
        _kc = kafka_config.get_config()
        self.kafka_config = {
            'bootstrap.servers': _kc['bootstrap_servers'],
            'group.id': _kc['group_id'],
            'auto.offset.reset': _kc['auto_offset_reset'],
            'enable.auto.commit': _kc['enable_auto_commit']
        }
        # Keep topic separately (not part of confluent_kafka config map)
        self.topic = _kc['topic']
        
        # Initialize technical indicators calculator
        self.indicators = TechnicalIndicators()
        
        # Initialize ARIMA forecaster
        self.arima_forecaster = MultiSymbolARIMAForecaster()
        
        # Initialize company manager
        self.company_manager = company_manager
        
        # Performance tracking
        self.messages_processed = 0
        self.errors_count = 0
        self.skipped_records = 0
        self.start_time = time.time()
        
        # Initialize Kafka consumer
        self.consumer = Consumer(self.kafka_config)
        
        # Database connection will be managed per operation using context managers
        # No persistent connection stored
        
    def _get_db_connection(self):
        """Get database connection from centralized manager"""
        from shared.database import db_manager
        return db_manager.get_connection()
    
    def _should_skip_extreme_values(self, indicators: Dict, ticker_symbol: str) -> bool:
        """Check if we should skip due to extreme values (non-trading hours)"""
        if not SKIP_EXTREME_VALUES:
            return False
            
        rsi = indicators.get('rsi')
        volatility = indicators.get('volatility')
        
        # Skip if RSI is exactly 100 or 0 (likely data quality issue during non-trading hours)
        if rsi is not None and (rsi == 100.0 or rsi == 0.0):
            logger.warning(f"Skipping {ticker_symbol} due to extreme RSI: {rsi}")
            return True
        
        # Skip if volatility is exactly 0 (no trading activity)
        if volatility is not None and volatility == 0.0:
            logger.warning(f"Skipping {ticker_symbol} due to zero volatility")
            return True
        
        return False
    
    def _insert_analytics_data(self, analytics_data: Dict, skip_retries_on_data_issues: bool = False) -> bool:
        """Insert analytics data into database with enhanced error handling"""
        max_retries = 1 if skip_retries_on_data_issues else 3
        for attempt in range(max_retries):
            db_conn = None
            try:
                db_conn = self._get_db_connection()
                with db_conn.cursor() as cur:
                    # Ensure timestamp is properly formatted
                    timestamp = analytics_data.get('timestamp')
                    if isinstance(timestamp, str):
                        timestamp = pd.Timestamp(timestamp).to_pydatetime()
                    elif timestamp is None:
                        timestamp = datetime.now(timezone.utc)
                    
                    # Convert NumPy types to native Python types for database compatibility
                    def convert_numpy_value(value):
                        """Convert NumPy types to native Python types"""
                        if value is None:
                            return None
                        # Handle NumPy scalar types
                        if hasattr(value, 'item'):  # NumPy scalars have .item() method
                            return value.item()
                        # Handle regular NumPy arrays (convert to float)
                        if hasattr(value, 'dtype'):
                            return float(value)
                        return value
                    
                    cur.execute("""
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
                    """, (
                        analytics_data['company_id'],
                        timestamp,
                        convert_numpy_value(analytics_data['current_price']),
                        convert_numpy_value(analytics_data.get('open_price')),
                        convert_numpy_value(analytics_data.get('high_price')),
                        convert_numpy_value(analytics_data.get('low_price')),
                        convert_numpy_value(analytics_data.get('volume')),
                        convert_numpy_value(analytics_data.get('rsi_14')),
                        convert_numpy_value(analytics_data.get('sma_20')),
                        convert_numpy_value(analytics_data.get('sma_50')),
                        convert_numpy_value(analytics_data.get('ema_12')),
                        convert_numpy_value(analytics_data.get('ema_26')),
                        convert_numpy_value(analytics_data.get('bb_upper')),
                        convert_numpy_value(analytics_data.get('bb_middle')),
                        convert_numpy_value(analytics_data.get('bb_lower')),
                        convert_numpy_value(analytics_data.get('macd')),
                        convert_numpy_value(analytics_data.get('macd_signal')),
                        convert_numpy_value(analytics_data.get('macd_histogram')),
                        convert_numpy_value(analytics_data.get('volatility')),
                        convert_numpy_value(analytics_data.get('price_change_percent')),
                        convert_numpy_value(analytics_data.get('volume_change_percent')),
                        convert_numpy_value(analytics_data.get('predicted_price')),
                        convert_numpy_value(analytics_data.get('prediction_confidence')),
                        analytics_data.get('model_type')  # String, no conversion needed
                    ))
                    db_conn.commit()
                    # Success - return connection and exit
                    from shared.database import db_manager
                    db_manager.put_connection(db_conn)
                    return True
                    
            except Exception as e:
                logger.error(f"Database insert attempt {attempt + 1} failed: {e}")
                if db_conn:
                    try:
                        db_conn.rollback()
                    except:
                        pass
                    # Return connection to pool after error
                    from shared.database import db_manager
                    db_manager.put_connection(db_conn)
                
                # Check if we should retry
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"Failed to insert analytics data for {analytics_data.get('ticker_symbol')} after {max_retries} attempts")
                    return False
        
        return False
    
    def _log_performance(self) -> None:
        """Log performance metrics"""
        conn = None
        try:
            from shared.database import db_manager
            conn = db_manager.get_connection()
            if not conn:
                logger.warning("Could not get database connection for performance logging")
                return
                
            current_timestamp = datetime.now(timezone.utc)
            processing_time_ms = (time.time() - self.start_time) * 1000
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO analytics_performance (
                        component_name, timestamp, processing_time_ms, messages_processed, errors_count
                    ) VALUES (%s, %s, %s, %s, %s)
                """, ('analytics_consumer', current_timestamp, processing_time_ms, self.messages_processed, self.errors_count))
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging performance: {e}")
            # Don't let performance logging errors break the main flow
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            if conn:
                db_manager.put_connection(conn)
    
    def _check_alerts(self, ticker_symbol: str, indicators: Dict) -> None:
        """Check for alert conditions"""
        try:
            rsi = indicators.get('rsi')
            volatility = indicators.get('volatility')
            
            # Get company_id for the ticker
            company_info = self.company_manager.get_company_by_ticker(ticker_symbol)
            if not company_info:
                logger.warning(f"Company info not found for {ticker_symbol}, skipping alerts")
                return
            
            company_id = company_info['company_id']
            alerts = []
            
            # RSI alerts
            if rsi is not None:
                if rsi > self.config['alert_thresholds']['rsi_overbought']:
                    alerts.append({
                        'type': 'RSI_OVERBOUGHT',
                        'value': rsi,
                        'threshold': self.config['alert_thresholds']['rsi_overbought'],
                        'message': f'RSI overbought: {rsi:.2f}',
                        'severity': 'HIGH'
                    })
                elif rsi < self.config['alert_thresholds']['rsi_oversold']:
                    alerts.append({
                        'type': 'RSI_OVERSOLD',
                        'value': rsi,
                        'threshold': self.config['alert_thresholds']['rsi_oversold'],
                        'message': f'RSI oversold: {rsi:.2f}',
                        'severity': 'HIGH'
                    })
            
            # Volatility alerts
            if volatility is not None and volatility > self.config['alert_thresholds']['volatility_threshold']:
                alerts.append({
                    'type': 'HIGH_VOLATILITY',
                    'value': volatility,
                    'threshold': self.config['alert_thresholds']['volatility_threshold'],
                    'message': f'High volatility detected: {volatility:.4f}',
                    'severity': 'MEDIUM'
                })
            
            # Insert alerts
            if alerts:
                conn = None
                try:
                    from shared.database import db_manager
                    conn = db_manager.get_connection()
                    if not conn:
                        logger.warning(f"Could not get database connection for alerts for {ticker_symbol}")
                        return
                        
                    for alert in alerts:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO analytics_alerts (
                                    company_id, alert_type, alert_message, indicator_value, 
                                    threshold_value, severity
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                            """, (company_id, alert['type'], alert['message'], alert['value'], alert['threshold'], alert['severity']))
                        conn.commit()
                        logger.info(f"Alert triggered for {ticker_symbol}: {alert['message']}")
                except Exception as alert_error:
                    logger.error(f"Error inserting alerts for {ticker_symbol}: {alert_error}")
                    if conn:
                        try:
                            conn.rollback()
                        except:
                            pass
                finally:
                    if conn:
                        db_manager.put_connection(conn)
                
        except Exception as e:
            logger.error(f"Error checking alerts for {ticker_symbol}: {e}")
    
    def process_message(self, stock_data: Dict) -> Optional[Dict]:
        """Process a single stock data message with enhanced error handling"""
        start_time = time.time()
        
        try:
            ticker_symbol = stock_data['ticker_symbol']
            current_price = stock_data['current_price']
            
            # Validate input data
            if not ticker_symbol or current_price is None or current_price <= 0:
                if SKIP_INVALID_DATA:
                    logger.warning(f"Skipping invalid data: {stock_data}")
                    return None
                else:
                    raise ValueError(f"Invalid stock data: {stock_data}")
            
            # Add price to technical indicators calculator
            self.indicators.add_price(ticker_symbol, current_price, stock_data.get('volume'))
            
            # Add price to ARIMA forecaster
            import pandas as pd
            timestamp = pd.Timestamp(stock_data.get('timestamp', datetime.now()))
            self.arima_forecaster.add_price(ticker_symbol, current_price, timestamp)
            
            # Calculate all technical indicators
            indicators = self.indicators.get_all_indicators(ticker_symbol)
            
            # Check if we should skip due to extreme values (non-trading hours)
            if self._should_skip_extreme_values(indicators, ticker_symbol):
                return None
            
            # Prepare analytics data
            analytics_data = {
                'company_id': stock_data['company_id'],
                'ticker_symbol': ticker_symbol,
                'timestamp': stock_data['timestamp'],
                'current_price': current_price,
                'open_price': stock_data.get('open_price'),
                'high_price': stock_data.get('high_price'),
                'low_price': stock_data.get('low_price'),
                'volume': stock_data.get('volume'),
                
                # Technical indicators
                'rsi_14': indicators.get('rsi'),
                'sma_20': indicators.get('sma_20'),
                'sma_50': indicators.get('sma_50'),
                'ema_12': indicators.get('ema_12'),
                'ema_26': indicators.get('ema_26'),
                'bb_upper': indicators.get('bollinger_upper'),
                'bb_middle': indicators.get('bollinger_middle'),
                'bb_lower': indicators.get('bollinger_lower'),
                'macd': indicators.get('macd_line'),
                'macd_signal': indicators.get('macd_signal'),
                'macd_histogram': indicators.get('macd_histogram'),
                'volatility': indicators.get('volatility'),
                
                # ARIMA predictions
                'predicted_price': None,
                'prediction_confidence': None,
                'model_type': 'ARIMA'
            }
            
            # Generate ARIMA forecast
            arima_failed_insufficient_data = False
            try:
                forecast = self.arima_forecaster.forecast_symbol(ticker_symbol, steps=1)
                if forecast.get('forecasts'):
                    analytics_data['predicted_price'] = forecast['forecasts'][0]
                    # Use AIC as a proxy for confidence (lower AIC = better model)
                    model_params = forecast.get('model_params', {})
                    aic = model_params.get('validation_metrics', {}).get('aic')
                    if aic:
                        # Convert AIC to a confidence score (0-1, higher is better)
                        analytics_data['prediction_confidence'] = max(0, min(1, 1 / (1 + abs(aic) / 100)))
            except Exception as e:
                error_msg = str(e).lower()
                if 'insufficient data' in error_msg:
                    logger.debug(f"ARIMA forecast skipped for {ticker_symbol}: insufficient data")
                    arima_failed_insufficient_data = True
                else:
                    logger.debug(f"ARIMA forecast not available for {ticker_symbol}: {e}")
            
            # Calculate price change percentage
            prices = self.indicators.get_price_history(ticker_symbol, limit=2)
            if len(prices) >= 2:
                price_change = ((current_price - prices[-2]) / prices[-2]) * 100
                analytics_data['price_change_percent'] = price_change
            
            # Store analytics data (skip if ARIMA failed due to insufficient data and no other meaningful data)
            if arima_failed_insufficient_data and not any([
                analytics_data.get('rsi_14'), analytics_data.get('sma_20'), 
                analytics_data.get('volatility')
            ]):
                logger.debug(f"Skipping analytics insert for {ticker_symbol}: insufficient data for meaningful analysis")
                return None
            
            if self._insert_analytics_data(analytics_data, skip_retries_on_data_issues=arima_failed_insufficient_data):
                self.messages_processed += 1
                
                # Check for alerts
                self._check_alerts(ticker_symbol, indicators)
                
                # Log performance periodically
                if self.messages_processed % 100 == 0:
                    processing_time = int((time.time() - start_time) * 1000)
                    self._log_performance(processing_time)
                    logger.info(f"Processed {self.messages_processed} messages, {self.errors_count} errors")
                
                return analytics_data
            else:
                self.errors_count += 1
                return None
                
        except Exception as e:
            self.errors_count += 1
            logger.error(f"Error processing message: {e}")
            return None
    
    def run(self):
        """Main consumer loop"""
        try:
            self.consumer.subscribe([self.topic])
            logger.info(f"Analytics consumer started, subscribed to {self.topic}")
            logger.info(f"Message limit: {MAX_MESSAGES if MAX_MESSAGES > 0 else 'unlimited'}")
            
            while True:
                msg = self.consumer.poll(1.0)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Parse message
                    data = json.loads(msg.value().decode('utf-8'))
                    
                    # Process analytics
                    analytics_result = self.process_message(data)
                    
                    if analytics_result:
                        # Get RSI and volatility values with null checks
                        rsi_value = analytics_result.get('rsi_14')
                        vol_value = analytics_result.get('volatility')
                        
                        # Format values safely
                        rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "N/A"
                        vol_str = f"{vol_value:.4f}" if vol_value is not None else "N/A"
                        
                        logger.info(f"Analytics processed for {data['ticker_symbol']}: RSI={rsi_str}, Vol={vol_str}")
                    
                    # Commit offset
                    self.consumer.commit(msg)
                    
                    # Check message limit
                    if MAX_MESSAGES > 0 and self.messages_processed >= MAX_MESSAGES:
                        logger.info(f"Reached message limit of {MAX_MESSAGES}. Stopping analytics consumer.")
                        break
                    
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    self.errors_count += 1
                    
        except KeyboardInterrupt:
            logger.info("Analytics consumer stopping...")
        except Exception as e:
            logger.error(f"Analytics consumer error: {e}")
        finally:
            self.consumer.close()
            # No persistent db_conn to clean up - connections are managed per operation
            logger.info("Analytics consumer stopped")

if __name__ == "__main__":
    consumer = AnalyticsConsumer()
    consumer.run() 