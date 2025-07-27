-- Analytics Schema for Real-time Stock Analysis
-- This extends the base schema with analytics capabilities

-- Real-time analytics results table
CREATE TABLE IF NOT EXISTS stock_analytics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Price data (denormalized for performance)
    current_price DECIMAL(10, 4) NOT NULL,
    open_price DECIMAL(10, 4),
    high_price DECIMAL(10, 4),
    low_price DECIMAL(10, 4),
    volume BIGINT,
    
    -- Technical indicators
    rsi_14 DECIMAL(10, 4),
    sma_20 DECIMAL(10, 4),
    sma_50 DECIMAL(10, 4),
    ema_12 DECIMAL(10, 4),
    ema_26 DECIMAL(10, 4),
    bollinger_upper DECIMAL(10, 4),
    bollinger_lower DECIMAL(10, 4),
    bollinger_middle DECIMAL(10, 4),
    macd_line DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_histogram DECIMAL(10, 4),
    
    -- Statistical measures
    volatility_20 DECIMAL(10, 4),
    price_change_pct DECIMAL(10, 4),
    volume_change_pct DECIMAL(10, 4),
    
    -- ML predictions
    predicted_price_1h DECIMAL(10, 4),
    predicted_price_1d DECIMAL(10, 4),
    prediction_confidence DECIMAL(10, 4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexing strategy for analytics
CREATE INDEX IF NOT EXISTS idx_analytics_symbol_time ON stock_analytics (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON stock_analytics (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_rsi ON stock_analytics (symbol, rsi_14) WHERE rsi_14 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_volatility ON stock_analytics (symbol, volatility_20) WHERE volatility_20 IS NOT NULL;

-- ML model metadata table
CREATE TABLE IF NOT EXISTS ml_models (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_path VARCHAR(255),
    accuracy DECIMAL(10, 4),
    last_trained TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Analytics alerts table
CREATE TABLE IF NOT EXISTS analytics_alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    alert_value DECIMAL(10, 4),
    threshold_value DECIMAL(10, 4),
    message TEXT,
    is_triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance monitoring table
CREATE TABLE IF NOT EXISTS analytics_performance (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(50) NOT NULL,
    processing_time_ms INTEGER,
    messages_processed INTEGER,
    errors_count INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Create materialized view for common analytics queries
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_analytics_summary AS
SELECT 
    symbol,
    DATE(timestamp) as date,
    AVG(current_price) as avg_price,
    MAX(current_price) as max_price,
    MIN(current_price) as min_price,
    AVG(rsi_14) as avg_rsi,
    AVG(volatility_20) as avg_volatility,
    COUNT(*) as data_points
FROM stock_analytics 
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY symbol, DATE(timestamp)
ORDER BY symbol, date DESC;

-- Refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_analytics_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_analytics_summary;
END;
$$ LANGUAGE plpgsql; 