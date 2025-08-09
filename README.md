# 📈 Real-time Stock Market Data Pipeline

> A modern, scalable real-time stock market data pipeline built with Apache Kafka, PostgreSQL, advanced analytics, machine learning, and interactive visualization.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-2.8+-orange.svg)](https://kafka.apache.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Features

### 🔄 Core Data Pipeline
- **Real-time Data Ingestion**: Yahoo Finance API integration with robust error handling
- **Message Streaming**: Apache Kafka with producer/consumer architecture
- **Data Persistence**: PostgreSQL with optimized schemas for historical and real-time data
- **Company Management**: Centralized company and industry data with automatic initialization
- **Centralized Configuration**: Unified config system across all components

### 📊 Advanced Analytics & ML
- **Technical Indicators**: RSI, SMA, EMA, Bollinger Bands, MACD, Volatility with OOP design
- **ARIMA Forecasting**: Statistical time series forecasting with automatic parameter selection
- **Real-time Processing**: Stream analytics with configurable calculation frequencies
- **Machine Learning**: Linear regression models with automated retraining
- **Performance Optimization**: Intelligent caching, batching, and frequency control

### 📱 Interactive Visualization
- **Modern Dashboard**: Responsive Dash/Plotly interface with real-time updates
- **Technical Analysis Charts**: Comprehensive indicator visualization
- **Alert System**: Real-time threshold monitoring with configurable alerts
- **Time Series Analysis**: Flexible data viewing with multiple time windows
- **Performance Metrics**: Live analytics performance tracking

### 🔧 Monitoring & Control
- **Pipeline Management**: Centralized start/stop control with health monitoring
- **Error Handling**: Comprehensive logging with database error tracking
- **Debug Support**: Optional runtime debugging with masked credential logging
- **Performance Monitoring**: Real-time analytics performance tracking
- **Configurable Operations**: Flexible message limits and processing controls

## Quick Start

### Prerequisites
- Python 3.8+
- Apache Kafka (with Zookeeper)
- PostgreSQL 12+
- pip install -r requirements.txt

### 🔧 Environment Setup

Create a `.env` file in the project root with **all required configuration**:

<details>
<summary><strong>📋 Complete .env Configuration Template</strong></summary>

```env
# =============================================================================
# KAFKA CONFIGURATION
# =============================================================================
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=stock-prices
KAFKA_GROUP_ID=stock-analytics
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_ENABLE_AUTO_COMMIT=true

# =============================================================================
# POSTGRESQL DATABASE CONFIGURATION
# =============================================================================
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=stocks
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
# Optional: Use DSN for complex connection strings
# POSTGRES_DSN=postgresql://user:pass@host:port/dbname

# =============================================================================
# PRODUCER CONFIGURATION
# =============================================================================
TICKERS=AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA,NFLX,AMD,INTC
POLL_INTERVAL=10

# =============================================================================
# TECHNICAL INDICATORS CONFIGURATION
# =============================================================================
# Window sizes for technical indicators
RSI_PERIOD=14
SMA_SHORT_PERIOD=20
SMA_LONG_PERIOD=50
EMA_SHORT_PERIOD=12
EMA_LONG_PERIOD=26
BOLLINGER_PERIOD=20
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
VOLATILITY_PERIOD=20

# Calculation frequencies (1 = every message, 5 = every 5th message)
RSI_CALC_FREQUENCY=1
SMA_CALC_FREQUENCY=1
EMA_CALC_FREQUENCY=1
BOLLINGER_CALC_FREQUENCY=5
MACD_CALC_FREQUENCY=1
VOLATILITY_CALC_FREQUENCY=5

# =============================================================================
# ANALYTICS ALERT THRESHOLDS
# =============================================================================
RSI_OVERBOUGHT=70.0
RSI_OVERSOLD=30.0
VOLATILITY_THRESHOLD=0.05
PRICE_CHANGE_THRESHOLD=0.05
VOLUME_CHANGE_THRESHOLD=2.0

# =============================================================================
# MACHINE LEARNING CONFIGURATION
# =============================================================================
# Linear Regression Model
LR_MODEL_PATH=ml/linear_regression_model.joblib
ML_WINDOW_SIZE=5
PREDICTION_HORIZON=1
RETRAIN_FREQUENCY=1000
MIN_TRAINING_SAMPLES=100
TEST_SIZE=0.2
RANDOM_STATE=42

# ARIMA Forecasting Configuration
ARIMA_MAX_P=5
ARIMA_MAX_D=2
ARIMA_MAX_Q=5
ARIMA_SEASONAL=false
ARIMA_FORECAST_STEPS=5
ARIMA_CONFIDENCE_LEVEL=0.95
ARIMA_MIN_OBSERVATIONS=50

# =============================================================================
# PERFORMANCE & ERROR HANDLING
# =============================================================================
# Performance settings
MAX_MESSAGES=0                    # 0 = unlimited
BATCH_SIZE=100
CACHE_SIZE=1000
LOG_PERFORMANCE_FREQUENCY=100

# Error handling
SKIP_INVALID_DATA=true
SKIP_EXTREME_VALUES=true
STOP_ON_CRITICAL_ERROR=false
MAX_RETRIES=3
RETRY_DELAY=0.5

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
# LOG_FILE_PATH=logs/pipeline.log  # Optional file logging

# =============================================================================
# DEBUGGING (Optional - for troubleshooting)
# =============================================================================
# DEBUG_DB_CONFIG=1              # Log masked DB config
# DEBUG_DB_BREAKPOINT=1          # Drop into debugger before DB connect
```

</details>

### Initialize Database
```bash
# Create database and run enhanced schema
psql -U postgres -d stocks -f db/enhanced_schema.sql
```

### Running the Pipeline

#### Option 1: Start All Components
```bash
python start_pipeline.py
```

#### Option 2: Start Individual Components
```bash
# Start Producer
python -m producer.producer

# Start Consumer
python -m consumer.consumer

# Start Analytics Consumer
python -m analytics.analytics_consumer

# Start Dashboard
python start_dashboard.py
```

### Dashboard
Access the dashboard at: http://localhost:8050

Features:
- Real-time stock price charts
- Technical indicators visualization
- Volatility analysis
- Recent alerts display
- Summary statistics
- Time window selection

### Configuration

The application uses a centralized configuration system via `shared/config.py` that manages:

#### Database Configuration
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `POSTGRES_DSN`: Optional single connection string override

#### Kafka Configuration
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses
- `KAFKA_TOPIC`: Topic name for stock data
- `KAFKA_GROUP_ID`: Consumer group identifier
- `KAFKA_AUTO_OFFSET_RESET`: Offset reset policy
- `KAFKA_ENABLE_AUTO_COMMIT`: Auto-commit configuration

#### Producer Configuration
- `TICKERS`: Comma-separated list of stock tickers
- `POLL_INTERVAL`: Data polling interval in seconds

#### Analytics Configuration
- Alert thresholds: `ALERT_RSI_OVERBOUGHT`, `ALERT_RSI_OVERSOLD`, `ALERT_VOLUME_SPIKE`, `ALERT_PRICE_CHANGE`
- Calculation frequencies for different indicators
- Window sizes for technical indicators

#### ML Configuration
- `ML_MODEL_UPDATE_FREQUENCY`: Model retraining frequency
- `ML_PREDICTION_CONFIDENCE_THRESHOLD`: Minimum confidence for predictions

#### Performance Settings
- `PERFORMANCE_CACHE_SIZE`: Maximum cache size for price history
- `PERFORMANCE_BATCH_SIZE`: Batch processing size

### Ticker Configuration
Default tickers: AAPL, MSFT, GOOGL, AMZN, TSLA
Add more tickers in the `.env` file or modify the producer configuration.

## Development

### Project Structure
```
real-time-stock-market-data-pipeline/
├── shared/                          # Centralized shared modules
│   ├── __init__.py
│   ├── config.py                   # Centralized configuration management
│   ├── database.py                 # Database connection and operations
│   └── error_handling.py           # Common error handling utilities
├── producer/
│   ├── __init__.py
│   └── producer.py                 # Stock data producer (refactored)
├── consumer/
│   ├── __init__.py
│   ├── consumer.py
│   └── db.py                       # Consumer database utilities
├── analytics/
│   ├── __init__.py
│   ├── analytics_consumer.py      # Enhanced analytics with ARIMA integration
│   └── technical_indicators_refactored.py  # Refactored technical indicators (to be removed)
├── dashboard/
│   ├── __init__.py
│   ├── app.py
│   └── README.md
├── ml/
│   ├── __init__.py
│   ├── arima_forecasting.py        # ARIMA statistical forecasting
│   ├── train_linear_regression.py  # ML model training
│   └── batch_predict_linear_regression.py  # Batch predictions
│   ├── __init__.py
│   └── company_manager.py
├── db/
│   └── enhanced_schema.sql
├── docs/
│   └── system_design.puml
├── .env                            # Environment configuration
├── .gitignore
├── docker-compose.yml
├── ERRORS_AND_FIXES.md
├── monitor_pipeline.ps1
├── start_pipeline.py
├── start_dashboard.py
├── requirements.txt
└── README.md
```

### Key Components

#### Producer
- **Centralized Configuration**: Uses shared config modules for consistency
- **Yahoo Finance Integration**: Fetches real-time stock data
- **Kafka Publishing**: Streams data to Kafka topics with error handling
- **Company Management**: Integrates with centralized company data
- **Robust Error Handling**: Comprehensive logging and retry mechanisms

#### Consumer
- **Real-time Processing**: Processes Kafka messages in real-time
- **Database Storage**: Stores data in PostgreSQL with optimized queries
- **Error Handling**: Robust error handling with rollback capabilities

#### Analytics
- **Refactored Technical Indicators**: Object-oriented design with caching and decorators
- **ARIMA Forecasting**: Statistical time series forecasting with automatic parameter selection
- **Real-time Processing**: Streams analytics data with configurable frequencies
- **Alert System**: Threshold-based monitoring with centralized configuration
- **Performance Optimization**: Caching, batching, and frequency control
- **Centralized Configuration**: Uses shared config for all settings

#### Dashboard
- **Interactive Charts**: Real-time price and technical indicator charts
- **Dynamic Data**: Auto-refreshing data with configurable intervals
- **Time Windows**: Flexible data viewing options

#### Utils
- **Company Manager**: Centralized company and industry management
- **Database Helpers**: Utility functions for database operations
- **Yahoo Finance Integration**: Company data fetching and management

## Recent Improvements

### Completed Refactoring
- [x] **Modular Architecture**: Centralized shared modules for config and database
- [x] **Configuration Management**: Single source of truth for all settings
- [x] **Database Operations**: Centralized with retry logic and error handling
- [x] **Technical Indicators**: Refactored with OOP design, caching, and decorators
- [x] **ARIMA Forecasting**: Statistical time series forecasting integration
- [x] **Error Handling**: Robust error handling across all components
- [x] **Code Deduplication**: Removed redundant code and centralized common logic

### Architecture Benefits
- **Maintainability**: Centralized configuration and database access
- **Consistency**: All components use shared modules
- **Debugging**: Enhanced debugging capabilities with optional breakpoints
- **Performance**: Optimized caching and batch processing
- **Extensibility**: Clean interfaces for adding new indicators and features

## Future Enhancements

### Short-term Goals
- [ ] Remove obsolete files (analytics/config.py, producer/config.py)
- [ ] Enhanced analytics consumer with ARIMA integration
- [ ] Advanced ML models (Random Forest, LSTM)
- [ ] Real-time sentiment analysis
- [ ] Portfolio tracking features

### Medium-term Goals
- [ ] Microservices architecture
- [ ] Kubernetes deployment
- [ ] API endpoints for external integrations
- [ ] Mobile dashboard application
- [ ] Advanced alerting (email, SMS, webhooks)

### Long-term Goals
- [ ] Multi-asset support (crypto, forex, commodities)
- [ ] Advanced ML pipeline with feature engineering
- [ ] Real-time news sentiment integration
- [ ] Social media sentiment analysis
- [ ] Regulatory compliance features
- [ ] Enterprise-grade security and authentication

## Troubleshooting

### Common Issues
1. **Kafka Connection**: Ensure Kafka and Zookeeper are running
2. **Database Connection**: Verify PostgreSQL is running and credentials are correct
3. **Missing Data**: Check if tickers are valid and data is available
4. **Dashboard Issues**: Ensure all required packages are installed

### Error Documentation
See `ERRORS_AND_FIXES.md` for detailed error solutions and troubleshooting steps.

### Monitoring Tools
- **Pipeline Monitor**: Use `monitor_pipeline.ps1` for Windows monitoring
- **Database Queries**: Check `db/enhanced_schema.sql` for useful queries
- **Log Files**: Check console output for detailed error messages

## Documentation

- **System Design**: See `docs/system_design.puml` for architecture diagrams
- **Error Guide**: See `ERRORS_AND_FIXES.md` for troubleshooting
- **API Documentation**: Available in component docstrings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Acknowledgments

- Yahoo Finance for stock data
- Apache Kafka for streaming
- PostgreSQL for data persistence
- Dash/Plotly for visualization
- Scikit-learn for machine learning 