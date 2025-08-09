"""
Shared Configuration Module
Centralizes all configuration loading and environment variable management
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variable parsing helpers
def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable"""
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')

def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_float(key: str, default: float = 0.0) -> float:
    """Get float environment variable"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': get_env_int('POSTGRES_PORT', 5432),
            'database': os.getenv('POSTGRES_DB', 'stocks'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get database configuration dictionary"""
        return self.config.copy()


class KafkaConfig:
    """Kafka configuration management"""
    
    def __init__(self):
        self.config = {
            'bootstrap_servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS') or os.getenv('KAFKA_BROKER', 'localhost:9092'),
            'topic': os.getenv('KAFKA_TOPIC', 'stock-prices'),
            'group_id': os.getenv('KAFKA_GROUP_ID', 'stock-analytics'),
            'auto_offset_reset': os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest'),
            'enable_auto_commit': get_env_bool('KAFKA_ENABLE_AUTO_COMMIT', True),
            'value_deserializer': 'json'
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get Kafka configuration dictionary"""
        return self.config.copy()
    
    def get_producer_config(self) -> Dict[str, Any]:
        """Get Kafka producer specific configuration"""
        return {
            'bootstrap_servers': self.config['bootstrap_servers'],
            'value_serializer': 'json'
        }
    
    def get_consumer_config(self) -> Dict[str, Any]:
        """Get Kafka consumer specific configuration"""
        return {
            'bootstrap_servers': self.config['bootstrap_servers'],
            'group_id': self.config['group_id'],
            'auto_offset_reset': self.config['auto_offset_reset'],
            'enable_auto_commit': self.config['enable_auto_commit']
        }


class AnalyticsConfig:
    """Analytics and technical indicators configuration"""
    
    def __init__(self):
        # Window sizes for technical indicators
        self.window_sizes = {
            'rsi_period': get_env_int('RSI_PERIOD', 14),
            'sma_short_period': get_env_int('SMA_SHORT_PERIOD', 20),
            'sma_long_period': get_env_int('SMA_LONG_PERIOD', 50),
            'ema_short_period': get_env_int('EMA_SHORT_PERIOD', 12),
            'ema_long_period': get_env_int('EMA_LONG_PERIOD', 26),
            'bollinger_period': get_env_int('BOLLINGER_PERIOD', 20),
            'macd_fast': get_env_int('MACD_FAST', 12),
            'macd_slow': get_env_int('MACD_SLOW', 26),
            'macd_signal': get_env_int('MACD_SIGNAL', 9),
            'volatility_period': get_env_int('VOLATILITY_PERIOD', 20)
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            'rsi_overbought': get_env_float('RSI_OVERBOUGHT', 70.0),
            'rsi_oversold': get_env_float('RSI_OVERSOLD', 30.0),
            'volatility_threshold': get_env_float('VOLATILITY_THRESHOLD', 0.05),
            'price_change_threshold': get_env_float('PRICE_CHANGE_THRESHOLD', 0.05),
            'volume_change_threshold': get_env_float('VOLUME_CHANGE_THRESHOLD', 2.0)
        }
        
        # Calculation frequencies
        self.calculation_frequencies = {
            'rsi_frequency': get_env_int('RSI_CALC_FREQUENCY', 1),
            'sma_frequency': get_env_int('SMA_CALC_FREQUENCY', 1),
            'ema_frequency': get_env_int('EMA_CALC_FREQUENCY', 1),
            'bollinger_frequency': get_env_int('BOLLINGER_CALC_FREQUENCY', 5),
            'macd_frequency': get_env_int('MACD_CALC_FREQUENCY', 1),
            'volatility_frequency': get_env_int('VOLATILITY_CALC_FREQUENCY', 5)
        }
        
        # Error handling configuration
        self.error_handling = {
            'skip_invalid_data': get_env_bool('SKIP_INVALID_DATA', True),
            'skip_extreme_values': get_env_bool('SKIP_EXTREME_VALUES', True),
            'stop_on_critical_error': get_env_bool('STOP_ON_CRITICAL_ERROR', False),
            'max_retries': get_env_int('MAX_RETRIES', 3),
            'retry_delay': get_env_float('RETRY_DELAY', 0.5)
        }
        
        # Performance settings
        self.performance = {
            'max_messages': get_env_int('MAX_MESSAGES', 0),  # 0 = unlimited
            'batch_size': get_env_int('BATCH_SIZE', 100),
            'cache_size': get_env_int('CACHE_SIZE', 1000),
            'log_performance_frequency': get_env_int('LOG_PERFORMANCE_FREQUENCY', 100)
        }


class MLConfig:
    """Machine Learning configuration"""
    
    def __init__(self):
        self.config = {
            'model_path': os.getenv('LR_MODEL_PATH', 'ml/linear_regression_model.joblib'),
            'window_size': get_env_int('ML_WINDOW_SIZE', 5),
            'prediction_horizon': get_env_int('PREDICTION_HORIZON', 1),
            'retrain_frequency': get_env_int('RETRAIN_FREQUENCY', 1000),
            'min_training_samples': get_env_int('MIN_TRAINING_SAMPLES', 100),
            'test_size': get_env_float('TEST_SIZE', 0.2),
            'random_state': get_env_int('RANDOM_STATE', 42)
        }
        
        # ARIMA specific configuration
        self.arima_config = {
            'max_p': get_env_int('ARIMA_MAX_P', 5),
            'max_d': get_env_int('ARIMA_MAX_D', 2),
            'max_q': get_env_int('ARIMA_MAX_Q', 5),
            'seasonal': get_env_bool('ARIMA_SEASONAL', False),
            'forecast_steps': get_env_int('ARIMA_FORECAST_STEPS', 5),
            'confidence_level': get_env_float('ARIMA_CONFIDENCE_LEVEL', 0.95),
            'min_observations': get_env_int('ARIMA_MIN_OBSERVATIONS', 50)
        }


class LoggingConfig:
    """Logging configuration management"""
    
    def __init__(self):
        self.level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.format = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.file_path = os.getenv('LOG_FILE_PATH', None)
    
    def setup_logging(self, logger_name: Optional[str] = None) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, self.level))
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create formatter
        formatter = logging.Formatter(self.format)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if self.file_path:
            file_handler = logging.FileHandler(self.file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger


# New: Producer configuration
class ProducerConfig:
    """Producer-specific configuration"""
    
    def __init__(self):
        # Comma-separated tickers list
        self.tickers = [t.strip() for t in os.getenv('TICKERS', 'AAPL,MSFT,GOOGL,AMZN,TSLA').split(',') if t.strip()]
        # Polling interval between cycles (seconds)
        self.poll_interval = get_env_int('POLL_INTERVAL', 5)

    def get_config(self) -> Dict[str, Any]:
        return {
            'tickers': list(self.tickers),
            'poll_interval': self.poll_interval,
        }

# Global configuration instances
db_config = DatabaseConfig()
kafka_config = KafkaConfig()
analytics_config = AnalyticsConfig()
ml_config = MLConfig()
logging_config = LoggingConfig()
producer_config = ProducerConfig()

# Convenience functions for backward compatibility
def get_db_config() -> Dict[str, Any]:
    """Get database configuration"""
    return db_config.get_config()

def get_kafka_config() -> Dict[str, Any]:
    """Get Kafka configuration"""
    return kafka_config.get_config()

def setup_logging(logger_name: Optional[str] = None) -> logging.Logger:
    """Setup logging with global configuration"""
    return logging_config.setup_logging(logger_name)

def get_producer_config() -> Dict[str, Any]:
    """Get Producer configuration"""
    return producer_config.get_config()
