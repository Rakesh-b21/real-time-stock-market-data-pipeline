import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional
from confluent_kafka import Consumer, KafkaException
import psycopg2
from psycopg2.extras import RealDictCursor

from analytics.config import ANALYTICS_CONFIG, ANALYTICS_KAFKA_CONFIG, ANALYTICS_DB_CONFIG
from analytics.technical_indicators import TechnicalIndicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Get message limit from environment
MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '0'))  # 0 means run forever

class AnalyticsConsumer:
    """
    Real-time analytics consumer that processes stock data and calculates technical indicators
    """
    
    def __init__(self):
        self.config = ANALYTICS_CONFIG
        self.kafka_config = ANALYTICS_KAFKA_CONFIG
        self.db_config = ANALYTICS_DB_CONFIG
        
        # Initialize technical indicators calculator
        self.indicators = TechnicalIndicators()
        
        # Performance tracking
        self.messages_processed = 0
        self.errors_count = 0
        self.start_time = time.time()
        
        # Initialize Kafka consumer
        self.consumer = Consumer({
            'bootstrap.servers': self.kafka_config['bootstrap_servers'],
            'group.id': self.kafka_config['group_id'],
            'auto.offset.reset': self.kafka_config['auto_offset_reset'],
            'enable.auto.commit': self.kafka_config['enable_auto_commit']
        })
        
        # Initialize database connection
        self.db_conn = self._get_db_connection()
        
    def _get_db_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(
                dbname=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                host=self.db_config['host'],
                port=self.db_config['port']
            )
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def _insert_analytics_data(self, analytics_data: Dict) -> bool:
        """Insert analytics data into database"""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO stock_analytics (
                        symbol, timestamp, current_price, open_price, high_price, low_price, volume,
                        rsi_14, sma_20, sma_50, ema_12, ema_26,
                        bollinger_upper, bollinger_lower, bollinger_middle,
                        macd_line, macd_signal, macd_histogram,
                        volatility_20, price_change_pct, volume_change_pct,
                        predicted_price_1h, predicted_price_1d, prediction_confidence
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                """, (
                    analytics_data['symbol'],
                    analytics_data['timestamp'],
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
                    analytics_data.get('bollinger_upper'),
                    analytics_data.get('bollinger_lower'),
                    analytics_data.get('bollinger_middle'),
                    analytics_data.get('macd_line'),
                    analytics_data.get('macd_signal'),
                    analytics_data.get('macd_histogram'),
                    analytics_data.get('volatility_20'),
                    analytics_data.get('price_change_pct'),
                    analytics_data.get('volume_change_pct'),
                    analytics_data.get('predicted_price_1h'),
                    analytics_data.get('predicted_price_1d'),
                    analytics_data.get('prediction_confidence')
                ))
                self.db_conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error inserting analytics data for {analytics_data.get('symbol')}: {e}")
            self.db_conn.rollback()
            return False
    
    def _log_performance(self, processing_time_ms: int):
        """Log performance metrics"""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO analytics_performance (
                        component_name, processing_time_ms, messages_processed, errors_count
                    ) VALUES (%s, %s, %s, %s)
                """, ('analytics_consumer', processing_time_ms, self.messages_processed, self.errors_count))
                self.db_conn.commit()
        except Exception as e:
            logger.error(f"Error logging performance: {e}")
    
    def _check_alerts(self, symbol: str, indicators: Dict) -> None:
        """Check for alert conditions"""
        try:
            rsi = indicators.get('rsi')
            volatility = indicators.get('volatility')
            
            alerts = []
            
            # RSI alerts
            if rsi is not None:
                if rsi > self.config['alert_thresholds']['rsi_overbought']:
                    alerts.append({
                        'type': 'RSI_OVERBOUGHT',
                        'value': rsi,
                        'threshold': self.config['alert_thresholds']['rsi_overbought'],
                        'message': f'RSI overbought: {rsi:.2f}'
                    })
                elif rsi < self.config['alert_thresholds']['rsi_oversold']:
                    alerts.append({
                        'type': 'RSI_OVERSOLD',
                        'value': rsi,
                        'threshold': self.config['alert_thresholds']['rsi_oversold'],
                        'message': f'RSI oversold: {rsi:.2f}'
                    })
            
            # Volatility alerts
            if volatility is not None and volatility > self.config['alert_thresholds']['volatility_threshold']:
                alerts.append({
                    'type': 'HIGH_VOLATILITY',
                    'value': volatility,
                    'threshold': self.config['alert_thresholds']['volatility_threshold'],
                    'message': f'High volatility detected: {volatility:.4f}'
                })
            
            # Insert alerts
            for alert in alerts:
                with self.db_conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO analytics_alerts (
                            symbol, alert_type, alert_value, threshold_value, message
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (symbol, alert['type'], alert['value'], alert['threshold'], alert['message']))
                self.db_conn.commit()
                logger.info(f"Alert triggered for {symbol}: {alert['message']}")
                
        except Exception as e:
            logger.error(f"Error checking alerts for {symbol}: {e}")
    
    def process_message(self, stock_data: Dict) -> Optional[Dict]:
        """Process a single stock data message"""
        start_time = time.time()
        
        try:
            symbol = stock_data['symbol']
            current_price = stock_data['current_price']
            
            # Add price to technical indicators calculator
            self.indicators.add_price(symbol, current_price, stock_data.get('volume'))
            
            # Calculate all technical indicators
            indicators = self.indicators.get_all_indicators(symbol)
            
            # Prepare analytics data
            analytics_data = {
                'symbol': symbol,
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
                'bollinger_upper': indicators.get('bollinger_upper'),
                'bollinger_lower': indicators.get('bollinger_lower'),
                'bollinger_middle': indicators.get('bollinger_middle'),
                'macd_line': indicators.get('macd_line'),
                'macd_signal': indicators.get('macd_signal'),
                'macd_histogram': indicators.get('macd_histogram'),
                'volatility_20': indicators.get('volatility'),
                
                # Placeholder for ML predictions (to be implemented)
                'predicted_price_1h': None,
                'predicted_price_1d': None,
                'prediction_confidence': None
            }
            
            # Calculate price change percentage
            prices = list(self.indicators.price_history.get(symbol, []))
            if len(prices) >= 2:
                price_change = ((current_price - prices[-2]) / prices[-2]) * 100
                analytics_data['price_change_pct'] = price_change
            
            # Store analytics data
            if self._insert_analytics_data(analytics_data):
                self.messages_processed += 1
                
                # Check for alerts
                self._check_alerts(symbol, indicators)
                
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
            self.consumer.subscribe([self.kafka_config['topic']])
            logger.info(f"Analytics consumer started, subscribed to {self.kafka_config['topic']}")
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
                        vol_value = analytics_result.get('volatility_20')
                        
                        # Format values safely
                        rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "N/A"
                        vol_str = f"{vol_value:.4f}" if vol_value is not None else "N/A"
                        
                        logger.info(f"Analytics processed for {data['symbol']}: RSI={rsi_str}, Vol={vol_str}")
                    
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
            if self.db_conn:
                self.db_conn.close()
            logger.info("Analytics consumer stopped")

if __name__ == "__main__":
    consumer = AnalyticsConsumer()
    consumer.run() 