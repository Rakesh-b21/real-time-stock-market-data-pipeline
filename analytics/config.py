import os
from dotenv import load_dotenv

load_dotenv()

# Analytics Configuration
ANALYTICS_CONFIG = {
    'window_sizes': {
        'rsi': int(os.getenv('RSI_WINDOW', '14')),
        'sma_short': int(os.getenv('SMA_SHORT_WINDOW', '20')),
        'sma_long': int(os.getenv('SMA_LONG_WINDOW', '50')),
        'ema_short': int(os.getenv('EMA_SHORT_WINDOW', '12')),
        'ema_long': int(os.getenv('EMA_LONG_WINDOW', '26')),
        'bollinger': int(os.getenv('BOLLINGER_WINDOW', '20')),
        'volatility': int(os.getenv('VOLATILITY_WINDOW', '20')),
        'macd_fast': int(os.getenv('MACD_FAST_WINDOW', '12')),
        'macd_slow': int(os.getenv('MACD_SLOW_WINDOW', '26')),
        'macd_signal': int(os.getenv('MACD_SIGNAL_WINDOW', '9'))
    },
    
    'calculation_frequency': {
        'rsi': int(os.getenv('RSI_FREQ', '1')),           # Every tick
        'sma': int(os.getenv('SMA_FREQ', '1')),           # Every tick
        'ema': int(os.getenv('EMA_FREQ', '1')),           # Every tick
        'bollinger': int(os.getenv('BOLLINGER_FREQ', '1')), # Every tick
        'macd': int(os.getenv('MACD_FREQ', '5')),         # Every 5 ticks
        'volatility': int(os.getenv('VOLATILITY_FREQ', '1')) # Every tick
    },
    
    'prediction_settings': {
        'horizon_1h': int(os.getenv('PREDICTION_1H', '60')),  # minutes
        'horizon_1d': int(os.getenv('PREDICTION_1D', '1440')), # minutes
        'confidence_threshold': float(os.getenv('CONFIDENCE_THRESHOLD', '0.7')),
        'model_update_frequency': int(os.getenv('MODEL_UPDATE_FREQ', '24'))  # hours
    },
    
    'performance_settings': {
        'max_price_history': int(os.getenv('MAX_PRICE_HISTORY', '1000')),
        'batch_size': int(os.getenv('BATCH_SIZE', '100')),
        'cache_ttl': int(os.getenv('CACHE_TTL', '300')),  # seconds
        'processing_timeout': int(os.getenv('PROCESSING_TIMEOUT', '5000'))  # ms
    },
    
    'alert_thresholds': {
        'rsi_overbought': float(os.getenv('RSI_OVERBOUGHT', '70')),
        'rsi_oversold': float(os.getenv('RSI_OVERSOLD', '30')),
        'volatility_threshold': float(os.getenv('VOLATILITY_THRESHOLD', '0.05')),
        'price_change_threshold': float(os.getenv('PRICE_CHANGE_THRESHOLD', '0.02'))
    }
}

# Database configuration for analytics
ANALYTICS_DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'stocks'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

# Kafka configuration for analytics consumer
ANALYTICS_KAFKA_CONFIG = {
    'bootstrap_servers': os.getenv('KAFKA_BROKER', 'localhost:9092'),
    'topic': os.getenv('KAFKA_TOPIC', 'stock_market_data'),
    'group_id': os.getenv('ANALYTICS_KAFKA_GROUP', 'analytics_consumers'),
    'auto_offset_reset': 'earliest',
    'enable_auto_commit': False
} 