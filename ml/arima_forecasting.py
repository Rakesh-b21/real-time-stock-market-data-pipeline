import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Union
from collections import deque
import warnings
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.stats.diagnostic import acorr_ljungbox
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os
from shared.config import analytics_config

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ARIMAForecaster:
    """
    ARIMA-based statistical forecasting for stock prices
    """
    
    def __init__(self, symbol: str = None):
        # Map required settings from shared analytics_config
        self.performance = analytics_config.performance
        # Default to 24 hours between model updates if not explicitly configured
        self.model_update_frequency_hours = 24
        self.symbol = symbol
        self.model = None
        self.model_params = None
        # Use cache_size as a proxy for max price history if available
        self.price_history = deque(maxlen=self.performance.get('cache_size', 1000))
        self.forecast_cache = {}
        self.last_model_update = None
        
        # ARIMA parameters
        self.default_order = (1, 1, 1)  # (p, d, q)
        self.max_p = 5
        self.max_d = 2
        self.max_q = 5
        self.min_observations = 50
        
    def add_price(self, price: float, timestamp: pd.Timestamp = None) -> None:
        """Add new price observation"""
        if timestamp is None:
            timestamp = pd.Timestamp.now()
        
        self.price_history.append((timestamp, price))
        
        # Check if model needs updating
        if self._should_update_model():
            self._update_model()
    
    def _should_update_model(self) -> bool:
        """Determine if model should be updated"""
        if self.model is None:
            return len(self.price_history) >= self.min_observations
        
        # Update based on configured frequency
        if self.last_model_update is None:
            return True
        
        hours_since_update = (pd.Timestamp.now() - self.last_model_update).total_seconds() / 3600
        return hours_since_update >= self.model_update_frequency_hours
    
    def _prepare_data(self) -> pd.Series:
        """Prepare time series data for ARIMA modeling"""
        if len(self.price_history) < self.min_observations:
            raise ValueError(f"Insufficient data: {len(self.price_history)} < {self.min_observations}")
        
        # Convert to pandas Series
        timestamps, prices = zip(*self.price_history)
        ts = pd.Series(prices, index=pd.DatetimeIndex(timestamps))
        
        # Remove duplicates and sort
        ts = ts.groupby(ts.index).last().sort_index()
        
        return ts
    
    def _check_stationarity(self, ts: pd.Series, alpha: float = 0.05) -> Tuple[bool, float]:
        """Check if time series is stationary using Augmented Dickey-Fuller test"""
        try:
            result = adfuller(ts.dropna())
            p_value = result[1]
            is_stationary = p_value < alpha
            
            logger.info(f"Stationarity test - p-value: {p_value:.4f}, Stationary: {is_stationary}")
            return is_stationary, p_value
        except Exception as e:
            logger.error(f"Error in stationarity test: {e}")
            return False, 1.0
    
    def _auto_arima_order(self, ts: pd.Series) -> Tuple[int, int, int]:
        """Automatically determine optimal ARIMA order using AIC"""
        best_aic = float('inf')
        best_order = self.default_order
        
        # Check stationarity to determine d
        is_stationary, _ = self._check_stationarity(ts)
        d_values = [0] if is_stationary else [1, 2]
        
        logger.info("Searching for optimal ARIMA parameters...")
        
        for p in range(0, min(self.max_p + 1, len(ts) // 10)):
            for d in d_values:
                for q in range(0, min(self.max_q + 1, len(ts) // 10)):
                    try:
                        model = ARIMA(ts, order=(p, d, q))
                        fitted_model = model.fit()
                        
                        if fitted_model.aic < best_aic:
                            best_aic = fitted_model.aic
                            best_order = (p, d, q)
                            
                    except Exception as e:
                        continue
        
        logger.info(f"Optimal ARIMA order: {best_order} (AIC: {best_aic:.2f})")
        return best_order
    
    def _validate_model(self, fitted_model) -> Dict[str, float]:
        """Validate ARIMA model using diagnostic tests"""
        try:
            # Ljung-Box test for residual autocorrelation
            residuals = fitted_model.resid
            lb_stat, lb_pvalue = acorr_ljungbox(residuals, lags=10, return_df=False)
            
            # Calculate model metrics
            aic = fitted_model.aic
            bic = fitted_model.bic
            
            validation_metrics = {
                'aic': aic,
                'bic': bic,
                'ljung_box_pvalue': lb_pvalue[-1] if hasattr(lb_pvalue, '__len__') else lb_pvalue,
                'residual_std': np.std(residuals)
            }
            
            logger.info(f"Model validation - AIC: {aic:.2f}, BIC: {bic:.2f}")
            return validation_metrics
            
        except Exception as e:
            logger.error(f"Error in model validation: {e}")
            return {}
    
    def _update_model(self) -> None:
        """Update ARIMA model with latest data"""
        try:
            ts = self._prepare_data()
            
            # Find optimal parameters
            optimal_order = self._auto_arima_order(ts)
            
            # Fit model
            model = ARIMA(ts, order=optimal_order)
            fitted_model = model.fit()
            
            # Validate model
            validation_metrics = self._validate_model(fitted_model)
            
            # Store model and parameters
            self.model = fitted_model
            self.model_params = {
                'order': optimal_order,
                'validation_metrics': validation_metrics,
                'data_points': len(ts),
                'last_price': ts.iloc[-1]
            }
            
            self.last_model_update = pd.Timestamp.now()
            self.forecast_cache.clear()  # Clear cache after model update
            
            logger.info(f"ARIMA model updated successfully for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error updating ARIMA model: {e}")
    
    def forecast(self, steps: int = 1, confidence_level: float = 0.95) -> Dict[str, Union[List[float], np.ndarray]]:
        """
        Generate ARIMA forecast
        
        Args:
            steps: Number of periods to forecast
            confidence_level: Confidence level for prediction intervals
            
        Returns:
            Dictionary containing forecasts and confidence intervals
        """
        if self.model is None:
            if len(self.price_history) >= self.min_observations:
                self._update_model()
            else:
                raise ValueError("Insufficient data for forecasting")
        
        cache_key = f"{steps}_{confidence_level}"
        if cache_key in self.forecast_cache:
            return self.forecast_cache[cache_key]
        
        try:
            # Generate forecast
            forecast_result = self.model.forecast(steps=steps, alpha=1-confidence_level)
            
            if hasattr(forecast_result, 'predicted_mean'):
                # statsmodels >= 0.12
                forecasts = forecast_result.predicted_mean.values
                conf_int = forecast_result.conf_int().values
            else:
                # older versions
                forecasts = forecast_result
                conf_int = None
            
            result = {
                'forecasts': forecasts.tolist(),
                'confidence_intervals': conf_int.tolist() if conf_int is not None else None,
                'model_params': self.model_params,
                'forecast_timestamp': pd.Timestamp.now().isoformat()
            }
            
            # Cache result
            self.forecast_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating forecast: {e}")
            return {'forecasts': [], 'error': str(e)}
    
    def get_forecast_accuracy(self, actual_prices: List[float], forecasts: List[float]) -> Dict[str, float]:
        """Calculate forecast accuracy metrics"""
        if len(actual_prices) != len(forecasts):
            raise ValueError("Actual prices and forecasts must have same length")
        
        mae = mean_absolute_error(actual_prices, forecasts)
        mse = mean_squared_error(actual_prices, forecasts)
        rmse = np.sqrt(mse)
        
        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((np.array(actual_prices) - np.array(forecasts)) / np.array(actual_prices))) * 100
        
        return {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'mape': mape
        }
    
    def save_model(self, filepath: str) -> None:
        """Save ARIMA model to file"""
        if self.model is None:
            raise ValueError("No model to save")
        
        model_data = {
            'model': self.model,
            'params': self.model_params,
            'symbol': self.symbol,
            'last_update': self.last_model_update
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """Load ARIMA model from file"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.model_params = model_data['params']
        self.symbol = model_data.get('symbol', self.symbol)
        self.last_model_update = model_data.get('last_update')
        
        logger.info(f"Model loaded from {filepath}")


class MultiSymbolARIMAForecaster:
    """
    Manager for multiple ARIMA forecasters across different symbols
    """
    
    def __init__(self):
        self.forecasters: Dict[str, ARIMAForecaster] = {}
    
    def add_symbol(self, symbol: str) -> None:
        """Add a new symbol for forecasting"""
        if symbol not in self.forecasters:
            self.forecasters[symbol] = ARIMAForecaster(symbol)
            logger.info(f"Added ARIMA forecaster for {symbol}")
    
    def add_price(self, symbol: str, price: float, timestamp: pd.Timestamp = None) -> None:
        """Add price data for a symbol"""
        if symbol not in self.forecasters:
            self.add_symbol(symbol)
        
        self.forecasters[symbol].add_price(price, timestamp)
    
    def forecast_symbol(self, symbol: str, steps: int = 1, confidence_level: float = 0.95) -> Dict:
        """Generate forecast for a specific symbol"""
        if symbol not in self.forecasters:
            logger.warning(f"Symbol {symbol} not found in ARIMA forecasters")
            return None
        
        try:
            return self.forecasters[symbol].forecast(steps, confidence_level)
        except Exception as e:
            logger.error(f"Error forecasting {symbol}: {e}")
            return None
    
    def forecast_all_symbols(self, steps: int = 1, confidence_level: float = 0.95) -> Dict[str, Dict]:
        """Generate forecasts for all symbols"""
        results = {}
        
        for symbol in self.forecasters:
            try:
                results[symbol] = self.forecast_symbol(symbol, steps, confidence_level)
            except Exception as e:
                logger.error(f"Error forecasting {symbol}: {e}")
                results[symbol] = {'error': str(e)}
        
        return results
    
    def get_model_status(self) -> Dict[str, Dict]:
        """Get status of all models"""
        status = {}
        
        for symbol, forecaster in self.forecasters.items():
            status[symbol] = {
                'has_model': forecaster.model is not None,
                'data_points': len(forecaster.price_history),
                'last_update': forecaster.last_model_update.isoformat() if forecaster.last_model_update else None,
                'model_params': forecaster.model_params
            }
        
        return status
