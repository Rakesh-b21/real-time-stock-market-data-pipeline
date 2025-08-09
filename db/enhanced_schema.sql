-- Enhanced Database Schema for Real-time Stock Market Data Pipeline
-- This schema provides a comprehensive foundation for advanced analytics and ML

-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Industries Table
-- Stores a list of industries for categorization of companies
CREATE TABLE industries (
    industry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    industry_name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Companies Table
-- Stores core information about each company
CREATE TABLE companies (
    company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    industry_id UUID NOT NULL REFERENCES industries(industry_id),
    company_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255), -- Full legal name of the company
    ticker_symbol VARCHAR(10) UNIQUE NOT NULL, -- Primary ticker symbol for the company
    exchange VARCHAR(50), -- Exchange where the stock is traded (e.g., NASDAQ, NYSE)
    sector VARCHAR(255), -- Broader sector (e.g., Technology, Healthcare)
    country VARCHAR(100),
    city VARCHAR(100),
    website_url VARCHAR(255),
    description TEXT,
    employees_count INT,
    -- JSONB column for industry-specific or miscellaneous company details
    additional_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for companies table
CREATE INDEX idx_companies_ticker_symbol ON companies(ticker_symbol);
CREATE INDEX idx_companies_industry_id ON companies(industry_id);
CREATE INDEX idx_companies_sector ON companies(sector);

-- 3. Stock Prices Historical Table (SCD Type 2)
-- Stores historical end-of-day stock price data, tracking changes over time
CREATE TABLE stock_prices_historical (
    price_id BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(company_id),
    trade_date DATE NOT NULL,
    open_price NUMERIC(18, 4) NOT NULL,
    high_price NUMERIC(18, 4) NOT NULL,
    low_price NUMERIC(18, 4) NOT NULL,
    close_price NUMERIC(18, 4) NOT NULL,
    adjusted_close_price NUMERIC(18, 4) NOT NULL,
    volume BIGINT NOT NULL,
    -- SCD Type 2 fields
    start_date DATE NOT NULL, -- The date from which this record is valid
    end_date DATE,             -- The date until which this record is valid (NULL if current)
    is_current BOOLEAN NOT NULL DEFAULT TRUE, -- Flag to easily identify the current active record
    UNIQUE (company_id, trade_date, start_date) -- Ensure uniqueness for a specific historical record
);

-- Indexes for historical prices
CREATE INDEX idx_stock_prices_hist_company_date ON stock_prices_historical(company_id, trade_date DESC);
CREATE INDEX idx_stock_prices_hist_is_current ON stock_prices_historical(company_id, is_current) WHERE is_current = TRUE;

-- 4. Stock Prices Real-time Table
-- Stores the latest (real-time or near real-time) stock price data for quick access
CREATE TABLE stock_prices_realtime (
    company_id UUID PRIMARY KEY REFERENCES companies(company_id), -- PK is company_id for direct lookup of latest price
    trade_datetime TIMESTAMP WITH TIME ZONE NOT NULL, -- Timestamp of the latest price
    open_price NUMERIC(18, 4) NOT NULL,
    high_price NUMERIC(18, 4) NOT NULL,
    low_price NUMERIC(18, 4) NOT NULL,
    current_price NUMERIC(18, 4) NOT NULL, -- Could be last trade price or bid/ask midpoint
    volume BIGINT NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Financial Statements Table
-- Stores various financial statements (Income Statement, Balance Sheet, Cash Flow)
CREATE TABLE financial_statements (
    statement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(company_id),
    statement_type VARCHAR(50) NOT NULL, -- e.g., 'INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW'
    period_type VARCHAR(20) NOT NULL, -- e.g., 'ANNUAL', 'QUARTERLY'
    report_date DATE NOT NULL, -- The date the report was filed or covers
    fiscal_date_ending DATE NOT NULL, -- The end date of the fiscal period
    currency VARCHAR(10) NOT NULL, -- e.g., 'USD', 'EUR'
    -- JSONB to store the detailed financial line items
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, statement_type, period_type, fiscal_date_ending)
);

-- Index for financial statements
CREATE INDEX idx_financial_statements_company_type_period_date ON financial_statements(company_id, statement_type, period_type, fiscal_date_ending DESC);

-- 6. Company News Table
-- Stores news articles or significant events related to companies
CREATE TABLE company_news (
    news_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(company_id),
    published_date TIMESTAMP WITH TIME ZONE NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    news_url VARCHAR(500) UNIQUE,
    source VARCHAR(100),
    sentiment VARCHAR(50), -- e.g., 'positive', 'negative', 'neutral'
    sentiment_score NUMERIC(3, 2), -- Sentiment score between -1 and 1
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for news retrieval
CREATE INDEX idx_company_news_company_date ON company_news(company_id, published_date DESC);
CREATE INDEX idx_company_news_sentiment ON company_news(sentiment);

-- 7. Analytics Table (Enhanced)
-- Stores calculated technical indicators and analytics
CREATE TABLE stock_analytics (
    analytics_id BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(company_id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Price data
    current_price NUMERIC(18, 4) NOT NULL,
    open_price NUMERIC(18, 4),
    high_price NUMERIC(18, 4),
    low_price NUMERIC(18, 4),
    volume BIGINT,
    -- Technical indicators
    rsi_14 NUMERIC(10, 4),
    sma_20 NUMERIC(18, 4),
    sma_50 NUMERIC(18, 4),
    ema_12 NUMERIC(18, 4),
    ema_26 NUMERIC(18, 4),
    bb_upper NUMERIC(18, 4),
    bb_middle NUMERIC(18, 4),
    bb_lower NUMERIC(18, 4),
    macd NUMERIC(18, 4),
    macd_signal NUMERIC(18, 4),
    macd_histogram NUMERIC(18, 4),
    volatility NUMERIC(10, 4),
    -- ML predictions
    predicted_price NUMERIC(18, 4),
    prediction_confidence NUMERIC(5, 4),
    model_type VARCHAR(50),
    -- Additional analytics
    price_change_percent NUMERIC(10, 4),
    volume_change_percent NUMERIC(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for analytics
CREATE INDEX idx_stock_analytics_company_timestamp ON stock_analytics(company_id, timestamp DESC);
CREATE INDEX idx_stock_analytics_timestamp ON stock_analytics(timestamp DESC);

-- 8. ML Models Table
-- Stores metadata about trained ML models
CREATE TABLE ml_models (
    model_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL, -- e.g., 'LinearRegression', 'LSTM', 'RandomForest'
    company_id UUID REFERENCES companies(company_id), -- NULL for general models
    model_version VARCHAR(50) NOT NULL,
    model_path VARCHAR(500) NOT NULL, -- Path to saved model file
    training_date TIMESTAMP WITH TIME ZONE NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Model performance metrics
    accuracy NUMERIC(5, 4),
    mse NUMERIC(20, 4),
    mae NUMERIC(20, 4),
    r2_score NUMERIC(5, 4),
    -- Model parameters and features
    parameters JSONB,
    features JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for ML models
CREATE INDEX idx_ml_models_company_type ON ml_models(company_id, model_type);
CREATE INDEX idx_ml_models_active ON ml_models(is_active) WHERE is_active = TRUE;

-- 9. Predictions Table (Enhanced)
-- Stores ML prediction results
CREATE TABLE predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(company_id),
    model_id UUID NOT NULL REFERENCES ml_models(model_id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_price NUMERIC(18, 4) NOT NULL,
    predicted_date TIMESTAMP WITH TIME ZONE NOT NULL, -- When the prediction is for
    confidence_score NUMERIC(5, 4),
    prediction_type VARCHAR(50), -- e.g., 'next_price', 'trend', 'volatility'
    features_used JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for predictions
CREATE INDEX idx_predictions_company_timestamp ON predictions(company_id, timestamp DESC);
CREATE INDEX idx_predictions_model ON predictions(model_id);

-- 10. Analytics Alerts Table
-- Stores triggered alerts based on technical indicators
CREATE TABLE analytics_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(company_id),
    alert_type VARCHAR(100) NOT NULL, -- e.g., 'RSI_OVERSOLD', 'PRICE_BREAKOUT', 'VOLUME_SPIKE'
    alert_message TEXT NOT NULL,
    indicator_value NUMERIC(18, 4),
    threshold_value NUMERIC(18, 4),
    severity VARCHAR(20) NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for alerts
CREATE INDEX idx_analytics_alerts_company_severity ON analytics_alerts(company_id, severity);
CREATE INDEX idx_analytics_alerts_acknowledged ON analytics_alerts(is_acknowledged) WHERE is_acknowledged = FALSE;

-- 11. Analytics Performance Table
-- Stores performance metrics of the analytics consumer
CREATE TABLE analytics_performance (
    performance_id BIGSERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    processing_time_ms INTEGER,
    messages_processed INTEGER,
    errors_count INTEGER,
    memory_usage_mb NUMERIC(10, 2),
    cpu_usage_percent NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance tracking
CREATE INDEX idx_analytics_performance_component_timestamp ON analytics_performance(component_name, timestamp DESC);

-- 12. Ingestion Errors Table (Enhanced)
-- Stores detailed error information
CREATE TABLE ingestion_errors (
    error_id BIGSERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL, -- 'producer', 'consumer', 'analytics'
    company_id UUID REFERENCES companies(company_id),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_details JSONB,
    data_context JSONB, -- The data that caused the error
    retry_count INTEGER DEFAULT 0,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for error tracking
CREATE INDEX idx_ingestion_errors_component_type ON ingestion_errors(component_name, error_type);
CREATE INDEX idx_ingestion_errors_resolved ON ingestion_errors(is_resolved) WHERE is_resolved = FALSE;

-- Triggers to update 'updated_at' timestamp automatically
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for tables with updated_at columns
CREATE TRIGGER update_industries_timestamp
    BEFORE UPDATE ON industries
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_companies_timestamp
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- Insert default industries
INSERT INTO industries (industry_name, description) VALUES
('Technology', 'Technology companies including software, hardware, and internet services'),
('Healthcare', 'Healthcare companies including pharmaceuticals, biotechnology, and medical devices'),
('Financial Services', 'Banks, insurance companies, and other financial institutions'),
('Consumer Discretionary', 'Consumer goods and services companies'),
('Energy', 'Oil, gas, and renewable energy companies'),
('Industrials', 'Manufacturing, construction, and industrial services'),
('Materials', 'Mining, chemicals, and materials companies'),
('Consumer Staples', 'Food, beverage, and household products'),
('Real Estate', 'Real estate investment trusts and property companies'),
('Utilities', 'Electric, gas, and water utility companies'),
('Communication Services', 'Telecommunications and media companies'),
('Other', 'Other industries not classified above')
ON CONFLICT (industry_name) DO NOTHING;

-- Create materialized view for daily analytics summary
CREATE MATERIALIZED VIEW daily_analytics_summary AS
SELECT 
    c.company_id,
    c.ticker_symbol,
    c.company_name,
    i.industry_name,
    DATE(a.timestamp) as trade_date,
    AVG(a.current_price) as avg_price,
    MAX(a.current_price) as max_price,
    MIN(a.current_price) as min_price,
    SUM(a.volume) as total_volume,
    AVG(a.rsi_14) as avg_rsi,
    AVG(a.volatility) as avg_volatility,
    COUNT(*) as data_points
FROM stock_analytics a
JOIN companies c ON a.company_id = c.company_id
JOIN industries i ON c.industry_id = i.industry_id
GROUP BY c.company_id, c.ticker_symbol, c.company_name, i.industry_name, DATE(a.timestamp);

-- Create index on materialized view
CREATE INDEX idx_daily_analytics_summary_company_date ON daily_analytics_summary(company_id, trade_date DESC);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_daily_analytics_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_analytics_summary;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get company information by ticker
CREATE OR REPLACE FUNCTION get_company_by_ticker(ticker VARCHAR(10))
RETURNS TABLE(
    company_id UUID,
    company_name VARCHAR(255),
    ticker_symbol VARCHAR(10),
    industry_name VARCHAR(255),
    sector VARCHAR(255),
    exchange VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.company_id,
        c.company_name,
        c.ticker_symbol,
        i.industry_name,
        c.sector,
        c.exchange
    FROM companies c
    JOIN industries i ON c.industry_id = i.industry_id
    WHERE c.ticker_symbol = ticker;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get latest stock price by ticker
CREATE OR REPLACE FUNCTION get_latest_price_by_ticker(ticker VARCHAR(10))
RETURNS TABLE(
    company_id UUID,
    ticker_symbol VARCHAR(10),
    current_price NUMERIC(18, 4),
    trade_datetime TIMESTAMP WITH TIME ZONE,
    volume BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.company_id,
        c.ticker_symbol,
        r.current_price,
        r.trade_datetime,
        r.volume
    FROM stock_prices_realtime r
    JOIN companies c ON r.company_id = c.company_id
    WHERE c.ticker_symbol = ticker;
END;
$$ LANGUAGE plpgsql; 