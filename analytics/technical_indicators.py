import numpy as np
import pandas as pd
import logging
from collections import deque
from typing import Dict, List, Optional, Tuple
from analytics.config import ANALYTICS_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """
    Real-time technical indicators calculator optimized for streaming data
    """
    
    def __init__(self):
        self.config = ANALYTICS_CONFIG
        self.price_history = {}  # symbol -> deque of prices
        self.indicator_cache = {}  # symbol -> dict of cached indicators
        self.tick_counters = {}  # symbol -> tick counter for frequency control
        
    def _ensure_price_history(self, symbol: str, max_size: int = None) -> deque:
        """Ensure price history exists for symbol"""
        if symbol not in self.price_history:
            max_size = max_size or self.config['performance_settings']['max_price_history']
            self.price_history[symbol] = deque(maxlen=max_size)
            self.tick_counters[symbol] = 0
        return self.price_history[symbol]
    
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
    
    def calculate_rsi(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate RSI (Relative Strength Index)"""
        if not self.should_calculate('rsi', symbol):
            return self.indicator_cache.get(symbol, {}).get('rsi')
            
        period = period or self.config['window_sizes']['rsi']
        prices = list(self.price_history.get(symbol, []))
        
        if len(prices) < period + 1:
            return None
            
        try:
            # Calculate price changes
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Calculate average gains and losses
            avg_gains = float(np.mean(gains[-period:]))  # Convert to Python float
            avg_losses = float(np.mean(losses[-period:]))  # Convert to Python float
            
            if avg_losses == 0:
                rsi = 100.0
            else:
                rs = avg_gains / avg_losses
                rsi = 100.0 - (100.0 / (1.0 + rs))
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['rsi'] = rsi
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI for {symbol}: {e}")
            return None
    
    def calculate_sma(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if not self.should_calculate('sma', symbol):
            return self.indicator_cache.get(symbol, {}).get('sma')
            
        period = period or self.config['window_sizes']['sma_short']
        prices = list(self.price_history.get(symbol, []))
        
        if len(prices) < period:
            return None
            
        try:
            sma = float(np.mean(prices[-period:]))  # Convert to Python float
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['sma'] = sma
            
            return sma
            
        except Exception as e:
            logger.error(f"Error calculating SMA for {symbol}: {e}")
            return None
    
    def calculate_ema(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if not self.should_calculate('ema', symbol):
            return self.indicator_cache.get(symbol, {}).get('ema')
            
        period = period or self.config['window_sizes']['ema_short']
        prices = list(self.price_history.get(symbol, []))
        
        if len(prices) < period:
            return None
            
        try:
            multiplier = 2.0 / (period + 1)
            ema = float(prices[0])  # Convert to Python float
            
            for price in prices[1:]:
                ema = (float(price) * multiplier) + (ema * (1.0 - multiplier))
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['ema'] = ema
            
            return ema
            
        except Exception as e:
            logger.error(f"Error calculating EMA for {symbol}: {e}")
            return None
    
    def calculate_bollinger_bands(self, symbol: str, period: int = None, std_dev: float = 2) -> Optional[Tuple[float, float, float]]:
        """Calculate Bollinger Bands (upper, lower, middle)"""
        if not self.should_calculate('bollinger', symbol):
            cached = self.indicator_cache.get(symbol, {}).get('bollinger')
            return cached
            
        period = period or self.config['window_sizes']['bollinger']
        prices = list(self.price_history.get(symbol, []))
        
        if len(prices) < period:
            return None
            
        try:
            prices_array = np.array(prices[-period:])
            sma = float(np.mean(prices_array))  # Convert to Python float
            std = float(np.std(prices_array))  # Convert to Python float
            
            upper_band = sma + (std_dev * std)
            lower_band = sma - (std_dev * std)
            
            result = (upper_band, lower_band, sma)
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['bollinger'] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands for {symbol}: {e}")
            return None
    
    def calculate_macd(self, symbol: str) -> Optional[Tuple[float, float, float]]:
        """Calculate MACD (line, signal, histogram)"""
        if not self.should_calculate('macd', symbol):
            cached = self.indicator_cache.get(symbol, {}).get('macd')
            return cached
            
        prices = list(self.price_history.get(symbol, []))
        fast_period = self.config['window_sizes']['macd_fast']
        slow_period = self.config['window_sizes']['macd_slow']
        signal_period = self.config['window_sizes']['macd_signal']
        
        if len(prices) < slow_period + signal_period:
            return None
            
        try:
            # Calculate EMAs
            fast_ema = self._calculate_ema_from_prices(prices, fast_period)
            slow_ema = self._calculate_ema_from_prices(prices, slow_period)
            
            if fast_ema is None or slow_ema is None:
                return None
                
            macd_line = float(fast_ema - slow_ema)  # Convert to Python float
            
            # Calculate signal line (EMA of MACD line)
            # For simplicity, we'll use a simplified approach
            # In production, you'd maintain a separate history of MACD values
            macd_signal = macd_line  # Simplified - should be EMA of MACD line
            macd_histogram = float(macd_line - macd_signal)  # Convert to Python float
            
            result = (macd_line, macd_signal, macd_histogram)
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['macd'] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating MACD for {symbol}: {e}")
            return None
    
    def calculate_volatility(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate historical volatility"""
        if not self.should_calculate('volatility', symbol):
            return self.indicator_cache.get(symbol, {}).get('volatility')
            
        period = period or self.config['window_sizes']['volatility']
        prices = list(self.price_history.get(symbol, []))
        
        if len(prices) < period + 1:
            return None
            
        try:
            # Calculate returns
            returns = np.diff(prices) / prices[:-1]
            volatility = float(np.std(returns) * np.sqrt(252))  # Convert to Python float
            
            # Cache the result
            if symbol not in self.indicator_cache:
                self.indicator_cache[symbol] = {}
            self.indicator_cache[symbol]['volatility'] = volatility
            
            return volatility
            
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol}: {e}")
            return None
    
    def _calculate_ema_from_prices(self, prices: List[float], period: int) -> Optional[float]:
        """Helper method to calculate EMA from price list"""
        if len(prices) < period:
            return None
            
        multiplier = 2.0 / (period + 1)
        ema = float(prices[0])  # Convert to Python float
        
        for price in prices[1:]:
            ema = (float(price) * multiplier) + (ema * (1.0 - multiplier))
            
        return ema
    
    def get_all_indicators(self, symbol: str) -> Dict[str, Optional[float]]:
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