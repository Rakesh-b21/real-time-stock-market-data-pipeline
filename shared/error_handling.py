"""
Shared Error Handling and Validation Module
Centralizes error handling patterns, data validation, and retry logic
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def safe_calculation(func: Callable) -> Callable:
    """Decorator for safe calculation with error handling"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return None
    return wrapper


def retry_on_failure(max_retries: int = 3, delay: float = 0.5, 
                    exceptions: tuple = (Exception,)) -> Callable:
    """Decorator for retrying operations on failure"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger.error(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts")
                        raise
            return None
        return wrapper
    return decorator


def log_performance(func: Callable) -> Callable:
    """Decorator to log function performance"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000
            logger.debug(f"{func.__name__} executed in {execution_time:.2f}ms")
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"{func.__name__} failed after {execution_time:.2f}ms: {e}")
            raise
    return wrapper


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_stock_data(data: Dict) -> bool:
        """Validate stock data structure and values"""
        required_fields = ['ticker_symbol', 'current_price', 'company_id']
        
        # Check required fields
        for field in required_fields:
            if field not in data or data[field] is None:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Validate ticker symbol
        if not isinstance(data['ticker_symbol'], str) or not data['ticker_symbol'].strip():
            logger.warning(f"Invalid ticker symbol: {data.get('ticker_symbol')}")
            return False
        
        # Validate price
        try:
            price = float(data['current_price'])
            if price <= 0:
                logger.warning(f"Invalid price: {price}")
                return False
        except (ValueError, TypeError):
            logger.warning(f"Invalid price format: {data.get('current_price')}")
            return False
        
        # Validate volume if present
        if 'volume' in data and data['volume'] is not None:
            try:
                volume = int(data['volume'])
                if volume < 0:
                    logger.warning(f"Invalid volume: {volume}")
                    return False
            except (ValueError, TypeError):
                logger.warning(f"Invalid volume format: {data.get('volume')}")
                return False
        
        return True
    
    @staticmethod
    def validate_indicators(indicators: Dict, ticker_symbol: str) -> bool:
        """Validate technical indicators for extreme values"""
        if not indicators:
            return True
        
        # Check for extreme RSI values (likely data quality issues)
        rsi = indicators.get('rsi')
        if rsi is not None:
            if rsi == 100.0 or rsi == 0.0:
                logger.warning(f"Extreme RSI detected for {ticker_symbol}: {rsi}")
                return False
            if not (0 <= rsi <= 100):
                logger.warning(f"Invalid RSI value for {ticker_symbol}: {rsi}")
                return False
        
        # Check for zero volatility (no trading activity)
        volatility = indicators.get('volatility')
        if volatility is not None and volatility == 0.0:
            logger.warning(f"Zero volatility detected for {ticker_symbol}")
            return False
        
        # Check for negative prices in indicators
        price_indicators = ['sma_20', 'sma_50', 'ema_12', 'ema_26', 'bb_upper', 'bb_middle', 'bb_lower']
        for indicator in price_indicators:
            value = indicators.get(indicator)
            if value is not None and value <= 0:
                logger.warning(f"Invalid {indicator} value for {ticker_symbol}: {value}")
                return False
        
        return True
    
    @staticmethod
    def sanitize_timestamp(timestamp_value: Any) -> datetime:
        """Sanitize and convert timestamp to proper datetime"""
        if isinstance(timestamp_value, str):
            try:
                import pandas as pd
                return pd.Timestamp(timestamp_value).to_pydatetime()
            except Exception:
                logger.warning(f"Invalid timestamp string: {timestamp_value}")
                return datetime.now(timezone.utc)
        elif isinstance(timestamp_value, datetime):
            return timestamp_value
        elif timestamp_value is None:
            return datetime.now(timezone.utc)
        else:
            logger.warning(f"Unknown timestamp format: {type(timestamp_value)}")
            return datetime.now(timezone.utc)
    
    @staticmethod
    def sanitize_numeric_value(value: Any, default: float = 0.0) -> float:
        """Sanitize numeric values with fallback"""
        if value is None:
            return default
        
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid numeric value: {value}, using default: {default}")
            return default


class ErrorHandler:
    """Centralized error handling"""
    
    def __init__(self, skip_invalid_data: bool = True, 
                 skip_extreme_values: bool = True,
                 stop_on_critical_error: bool = False):
        self.skip_invalid_data = skip_invalid_data
        self.skip_extreme_values = skip_extreme_values
        self.stop_on_critical_error = stop_on_critical_error
        self.error_count = 0
        self.skipped_count = 0
    
    def handle_data_error(self, error: Exception, data: Dict, 
                         operation: str = "processing") -> bool:
        """Handle data processing errors"""
        self.error_count += 1
        logger.error(f"Error during {operation}: {error}")
        
        if self.skip_invalid_data:
            self.skipped_count += 1
            logger.warning(f"Skipping invalid data: {data}")
            return True  # Continue processing
        else:
            if self.stop_on_critical_error:
                logger.critical(f"Critical error during {operation}, stopping pipeline")
                raise error
            return False  # Stop processing this item
    
    def should_skip_extreme_values(self, indicators: Dict, ticker_symbol: str) -> bool:
        """Check if we should skip due to extreme values"""
        if not self.skip_extreme_values:
            return False
        
        if not DataValidator.validate_indicators(indicators, ticker_symbol):
            self.skipped_count += 1
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get error handling statistics"""
        return {
            'error_count': self.error_count,
            'skipped_count': self.skipped_count
        }


class PerformanceMonitor:
    """Performance monitoring utilities"""
    
    def __init__(self):
        self.start_time = time.time()
        self.message_count = 0
        self.error_count = 0
        self.last_log_time = time.time()
        self.processing_times = []
    
    def record_message(self, processing_time_ms: float):
        """Record message processing metrics"""
        self.message_count += 1
        self.processing_times.append(processing_time_ms)
        
        # Keep only last 1000 measurements for memory efficiency
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def record_error(self):
        """Record error occurrence"""
        self.error_count += 1
    
    def should_log_performance(self, frequency: int = 100) -> bool:
        """Check if it's time to log performance metrics"""
        return self.message_count % frequency == 0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        stats = {
            'uptime_seconds': uptime,
            'messages_processed': self.message_count,
            'errors_count': self.error_count,
            'messages_per_second': self.message_count / uptime if uptime > 0 else 0,
            'error_rate': self.error_count / self.message_count if self.message_count > 0 else 0
        }
        
        if self.processing_times:
            import statistics
            stats.update({
                'avg_processing_time_ms': statistics.mean(self.processing_times),
                'median_processing_time_ms': statistics.median(self.processing_times),
                'max_processing_time_ms': max(self.processing_times),
                'min_processing_time_ms': min(self.processing_times)
            })
        
        return stats


# Utility functions for common error handling patterns
def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback"""
    return DataValidator.sanitize_numeric_value(value, default)


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert value to int with default fallback"""
    try:
        return int(DataValidator.sanitize_numeric_value(value, default))
    except (ValueError, TypeError):
        return default


def is_trading_hours() -> bool:
    """Check if current time is during trading hours (basic implementation)"""
    current_time = datetime.now()
    # Simple check for weekdays between 9:30 AM and 4:00 PM EST
    # This is a simplified version - real implementation would consider holidays, etc.
    if current_time.weekday() >= 5:  # Weekend
        return False
    
    hour = current_time.hour
    return 9 <= hour <= 16  # Simplified trading hours check
