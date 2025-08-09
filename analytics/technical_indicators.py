import numpy as np
import pandas as pd
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, List, Optional, Tuple, Union, Any
from functools import wraps
from shared.config import analytics_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cached_indicator(func):
    """Decorator for caching indicator calculations"""
    @wraps(func)
    def wrapper(self, symbol: str, *args, **kwargs):
        indicator_name = func.__name__.replace('calculate_', '')
        
        # Check if calculation is needed based on frequency
        if not self.should_calculate(indicator_name, symbol):
            cached_value = self._get_cached_value(symbol, indicator_name)
            if cached_value is not None:
                return cached_value
        
        # Calculate new value
        try:
            result = func(self, symbol, *args, **kwargs)
            if result is not None:
                self._cache_value(symbol, indicator_name, result)
            return result
        except Exception as e:
            logger.error(f"Error calculating {indicator_name} for {symbol}: {e}")
            return None
    
    return wrapper


def safe_calculation(func):
    """Decorator for safe numerical calculations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ZeroDivisionError, ValueError, TypeError) as e:
            logger.warning(f"Calculation error in {func.__name__}: {e}")
            return None
    return wrapper


class BaseIndicator(ABC):
    """Base class for all technical indicators"""
    
    def __init__(self, name: str, default_period: int):
        self.name = name
        self.default_period = default_period
    
    @abstractmethod
    def calculate(self, prices: List[float], period: int = None) -> Optional[Union[float, Tuple]]:
        """Calculate the indicator value"""
        pass
    
    def validate_data(self, prices: List[float], min_length: int) -> bool:
        """Validate input data"""
        return len(prices) >= min_length


class RSIIndicator(BaseIndicator):
    """Relative Strength Index calculator"""
    
    def __init__(self):
        super().__init__("rsi", 14)
    
    @safe_calculation
    def calculate(self, prices: List[float], period: int = None) -> Optional[float]:
        period = period or self.default_period
        
        if not self.validate_data(prices, period + 1):
            return None
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = float(np.mean(gains[-period:]))
        avg_losses = float(np.mean(losses[-period:]))
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        return 100.0 - (100.0 / (1.0 + rs))


class SMAIndicator(BaseIndicator):
    """Simple Moving Average calculator"""
    
    def __init__(self):
        super().__init__("sma", 20)
    
    @safe_calculation
    def calculate(self, prices: List[float], period: int = None) -> Optional[float]:
        period = period or self.default_period
        
        if not self.validate_data(prices, period):
            return None
        
        return float(np.mean(prices[-period:]))


class EMAIndicator(BaseIndicator):
    """Exponential Moving Average calculator"""
    
    def __init__(self):
        super().__init__("ema", 12)
    
    @safe_calculation
    def calculate(self, prices: List[float], period: int = None) -> Optional[float]:
        period = period or self.default_period
        
        if not self.validate_data(prices, period):
            return None
        
        multiplier = 2.0 / (period + 1)
        ema = float(prices[0])
        
        for price in prices[1:]:
            ema = (float(price) * multiplier) + (ema * (1.0 - multiplier))
        
        return ema


class BollingerBandsIndicator(BaseIndicator):
    """Bollinger Bands calculator"""
    
    def __init__(self):
        super().__init__("bollinger", 20)
    
    @safe_calculation
    def calculate(self, prices: List[float], period: int = None, std_dev: float = 2) -> Optional[Tuple[float, float, float]]:
        period = period or self.default_period
        
        if not self.validate_data(prices, period):
            return None
        
        prices_array = np.array(prices[-period:])
        sma = float(np.mean(prices_array))
        std = float(np.std(prices_array))
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return (upper_band, lower_band, sma)


class MACDIndicator(BaseIndicator):
    """MACD calculator"""
    
    def __init__(self):
        super().__init__("macd", 26)
        self.ema_calculator = EMAIndicator()
    
    @safe_calculation
    def calculate(self, prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Optional[Tuple[float, float, float]]:
        if not self.validate_data(prices, slow_period + signal_period):
            return None
        
        fast_ema = self.ema_calculator.calculate(prices, fast_period)
        slow_ema = self.ema_calculator.calculate(prices, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = float(fast_ema - slow_ema)
        # Simplified signal line calculation - in production, maintain MACD history
        macd_signal = macd_line
        macd_histogram = float(macd_line - macd_signal)
        
        return (macd_line, macd_signal, macd_histogram)


class VolatilityIndicator(BaseIndicator):
    """Historical Volatility calculator"""
    
    def __init__(self):
        super().__init__("volatility", 20)
    
    @safe_calculation
    def calculate(self, prices: List[float], period: int = None) -> Optional[float]:
        period = period or self.default_period
        
        if not self.validate_data(prices, period + 1):
            return None
        
        returns = np.diff(prices) / prices[:-1]
        return float(np.std(returns) * np.sqrt(252))


class TechnicalIndicators:
    """
    Refactored real-time technical indicators calculator with improved architecture
    """
    
    def __init__(self):
        # Normalize shared analytics_config into the dict structure expected by this class
        self.config = {
            'performance_settings': analytics_config.performance,
            'calculation_frequency': {
                'rsi': analytics_config.calculation_frequencies['rsi_frequency'],
                'sma': analytics_config.calculation_frequencies['sma_frequency'],
                'ema': analytics_config.calculation_frequencies['ema_frequency'],
                'bollinger': analytics_config.calculation_frequencies['bollinger_frequency'],
                'macd': analytics_config.calculation_frequencies['macd_frequency'],
                'volatility': analytics_config.calculation_frequencies['volatility_frequency'],
            },
            'window_sizes': {
                'rsi': analytics_config.window_sizes['rsi_period'],
                'sma_short': analytics_config.window_sizes['sma_short_period'],
                'sma_long': analytics_config.window_sizes['sma_long_period'],
                'ema_short': analytics_config.window_sizes['ema_short_period'],
                'ema_long': analytics_config.window_sizes['ema_long_period'],
                'bollinger': analytics_config.window_sizes['bollinger_period'],
                'volatility': analytics_config.window_sizes['volatility_period'],
                'macd_fast': analytics_config.window_sizes['macd_fast'],
                'macd_slow': analytics_config.window_sizes['macd_slow'],
                'macd_signal': analytics_config.window_sizes['macd_signal'],
            }
        }
        self.price_history: Dict[str, deque] = {}
        self.indicator_cache: Dict[str, Dict[str, Any]] = {}
        self.tick_counters: Dict[str, int] = {}
        
        # Initialize indicator calculators
        self.indicators = {
            'rsi': RSIIndicator(),
            'sma': SMAIndicator(),
            'ema': EMAIndicator(),
            'bollinger': BollingerBandsIndicator(),
            'macd': MACDIndicator(),
            'volatility': VolatilityIndicator()
        }
    
    def _ensure_price_history(self, symbol: str, max_size: int = None) -> deque:
        """Ensure price history exists for symbol"""
        if symbol not in self.price_history:
            perf = self.config.get('performance_settings', {})
            # Prefer explicit max_price_history, else fallback to cache_size, else default 1000
            default_size = 1000
            max_size = max_size or perf.get('max_price_history') or perf.get('cache_size', default_size)
            self.price_history[symbol] = deque(maxlen=max_size)
            self.tick_counters[symbol] = 0
        return self.price_history[symbol]
    
    def _get_cached_value(self, symbol: str, indicator: str) -> Optional[Any]:
        """Get cached indicator value"""
        return self.indicator_cache.get(symbol, {}).get(indicator)
    
    def _cache_value(self, symbol: str, indicator: str, value: Any) -> None:
        """Cache indicator value"""
        if symbol not in self.indicator_cache:
            self.indicator_cache[symbol] = {}
        self.indicator_cache[symbol][indicator] = value
    
    def add_price(self, symbol: str, price: float, volume: Optional[int] = None) -> None:
        """Add new price to history"""
        history = self._ensure_price_history(symbol)
        history.append(price)
        self.tick_counters[symbol] += 1
    
    def should_calculate(self, indicator: str, symbol: str) -> bool:
        """Check if indicator should be calculated based on frequency"""
        freq = self.config['calculation_frequency'].get(indicator, 1)
        tick_count = self.tick_counters.get(symbol, 0)
        return tick_count % freq == 0
    
    @cached_indicator
    def calculate_rsi(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate RSI using the dedicated calculator"""
        period = period or self.config['window_sizes']['rsi']
        prices = list(self.price_history.get(symbol, []))
        return self.indicators['rsi'].calculate(prices, period)
    
    @cached_indicator
    def calculate_sma(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate SMA using the dedicated calculator"""
        period = period or self.config['window_sizes']['sma_short']
        prices = list(self.price_history.get(symbol, []))
        return self.indicators['sma'].calculate(prices, period)
    
    @cached_indicator
    def calculate_ema(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate EMA using the dedicated calculator"""
        period = period or self.config['window_sizes']['ema_short']
        prices = list(self.price_history.get(symbol, []))
        return self.indicators['ema'].calculate(prices, period)
    
    @cached_indicator
    def calculate_bollinger_bands(self, symbol: str, period: int = None, std_dev: float = 2) -> Optional[Tuple[float, float, float]]:
        """Calculate Bollinger Bands using the dedicated calculator"""
        period = period or self.config['window_sizes']['bollinger']
        prices = list(self.price_history.get(symbol, []))
        return self.indicators['bollinger'].calculate(prices, period, std_dev)
    
    @cached_indicator
    def calculate_macd(self, symbol: str) -> Optional[Tuple[float, float, float]]:
        """Calculate MACD using the dedicated calculator"""
        prices = list(self.price_history.get(symbol, []))
        fast_period = self.config['window_sizes']['macd_fast']
        slow_period = self.config['window_sizes']['macd_slow']
        signal_period = self.config['window_sizes']['macd_signal']
        return self.indicators['macd'].calculate(prices, fast_period, slow_period, signal_period)
    
    @cached_indicator
    def calculate_volatility(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate volatility using the dedicated calculator"""
        period = period or self.config['window_sizes']['volatility']
        prices = list(self.price_history.get(symbol, []))
        return self.indicators['volatility'].calculate(prices, period)
    
    def get_all_indicators(self, symbol: str) -> Dict[str, Optional[Union[float, Tuple]]]:
        """Calculate all indicators for a symbol"""
        indicators = {}
        
        # Add current price
        prices = list(self.price_history.get(symbol, []))
        if prices:
            indicators['current_price'] = prices[-1]
        
        # Calculate technical indicators
        indicators['rsi'] = self.calculate_rsi(symbol)
        indicators['sma_20'] = self.calculate_sma(symbol, 20)
        indicators['sma_50'] = self.calculate_sma(symbol, 50)
        indicators['ema_12'] = self.calculate_ema(symbol, 12)
        indicators['ema_26'] = self.calculate_ema(symbol, 26)
        indicators['volatility'] = self.calculate_volatility(symbol)
        
        # Calculate Bollinger Bands
        bb = self.calculate_bollinger_bands(symbol)
        if bb:
            indicators['bollinger_upper'], indicators['bollinger_lower'], indicators['bollinger_middle'] = bb
        
        # Calculate MACD
        macd = self.calculate_macd(symbol)
        if macd:
            indicators['macd_line'], indicators['macd_signal'], indicators['macd_histogram'] = macd
        
        return indicators
    
    def clear_cache(self, symbol: str = None) -> None:
        """Clear indicator cache"""
        if symbol:
            self.indicator_cache.pop(symbol, None)
        else:
            self.indicator_cache.clear()
    
    def get_price_history(self, symbol: str, limit: int = None) -> List[float]:
        """Get price history for a symbol"""
        prices = list(self.price_history.get(symbol, []))
        return prices[-limit:] if limit else prices
    
    def add_custom_indicator(self, name: str, indicator: BaseIndicator) -> None:
        """Add a custom indicator calculator"""
        self.indicators[name] = indicator
