-- Current Database Schema (Post-Migration)
-- This reflects the actual database structure after applying migration_realtime_changes.sql
-- Date: 2025-08-13
-- Status: Production Ready

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Companies Table
CREATE TABLE companies (
    company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Stock Prices Real-time Table (UPDATED SCHEMA)
-- Stores multiple real-time price records per company (allows historical tracking)
CREATE TABLE stock_prices_realtime (
    realtime_id BIGSERIAL PRIMARY KEY,                    -- Surrogate primary key
    company_id UUID NOT NULL REFERENCES companies(company_id),
    trade_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price NUMERIC(18, 4) NOT NULL,
    high_price NUMERIC(18, 4) NOT NULL,
    low_price NUMERIC(18, 4) NOT NULL,
    current_price NUMERIC(18, 4) NOT NULL,               -- Note: NOT close_price
    volume BIGINT NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_stock_prices_realtime_company_datetime ON stock_prices_realtime(company_id, trade_datetime DESC);
CREATE INDEX idx_stock_prices_realtime_latest ON stock_prices_realtime(company_id, last_updated DESC);

-- 3. Stock Prices Historical Table
CREATE TABLE stock_prices_historical (
    price_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(company_id),
    trade_date DATE NOT NULL,
    open_price NUMERIC(18, 4) NOT NULL,
    high_price NUMERIC(18, 4) NOT NULL,
    low_price NUMERIC(18, 4) NOT NULL,
    close_price NUMERIC(18, 4) NOT NULL,                 -- Historical table has close_price
    adjusted_close_price NUMERIC(18, 4),
    volume BIGINT NOT NULL,
    start_date DATE,                                      -- Made nullable by migration
    end_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, trade_date, is_current)
);

-- 4. Stock Analytics Table
CREATE TABLE stock_analytics (
    analytics_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(company_id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    current_price NUMERIC(18, 4) NOT NULL,
    open_price NUMERIC(18, 4),
    high_price NUMERIC(18, 4),
    low_price NUMERIC(18, 4),
    volume BIGINT,
    
    -- Technical Indicators
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
    price_change_percent NUMERIC(10, 4),
    volume_change_percent NUMERIC(10, 4),
    
    -- ML Predictions
    predicted_price NUMERIC(18, 4),
    prediction_confidence NUMERIC(5, 4),
    model_type VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for analytics queries
CREATE INDEX idx_stock_analytics_company_timestamp ON stock_analytics(company_id, timestamp DESC);

-- 5. Financial Statements Table
CREATE TABLE financial_statements (
    statement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(company_id),
    statement_type VARCHAR(50) NOT NULL,
    period_type VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    fiscal_date_ending DATE NOT NULL,
    currency VARCHAR(10) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, statement_type, period_type, fiscal_date_ending)
);

-- 6. Ingestion Errors Table
CREATE TABLE ingestion_errors (
    error_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component_name VARCHAR(100) NOT NULL,
    company_id UUID REFERENCES companies(company_id),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_details JSONB,
    data_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Performance Metrics Table
CREATE TABLE performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value NUMERIC(18, 4) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Migration Functions (from migration_realtime_changes.sql)

-- Function to get latest real-time data per company per date
CREATE OR REPLACE FUNCTION get_latest_realtime_per_date()
RETURNS TABLE(
    company_id UUID,
    ticker_symbol VARCHAR(10),
    trade_date DATE,
    open_price NUMERIC(18, 4),
    high_price NUMERIC(18, 4),
    low_price NUMERIC(18, 4),
    close_price NUMERIC(18, 4),
    volume BIGINT,
    trade_datetime TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (rt.company_id, DATE(rt.trade_datetime))
        rt.company_id,
        c.ticker_symbol,
        DATE(rt.trade_datetime) as trade_date,
        rt.open_price,
        rt.high_price,
        rt.low_price,
        rt.current_price as close_price,  -- Map current_price to close_price
        rt.volume,
        rt.trade_datetime
    FROM stock_prices_realtime rt
    JOIN companies c ON rt.company_id = c.company_id
    ORDER BY rt.company_id, DATE(rt.trade_datetime), rt.trade_datetime DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to migrate real-time data to historical
CREATE OR REPLACE FUNCTION migrate_realtime_to_historical()
RETURNS INTEGER AS $$
DECLARE
    inserted_count INTEGER := 0;
BEGIN
    -- Insert latest records per date from real-time to historical
    INSERT INTO stock_prices_historical (
        company_id, trade_date, open_price, high_price, low_price, 
        close_price, adjusted_close_price, volume, start_date, end_date, is_current
    )
    SELECT 
        company_id,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        close_price as adjusted_close_price, -- Assuming no adjustment for now
        volume,
        trade_date as start_date,
        trade_date as end_date,
        TRUE as is_current
    FROM get_latest_realtime_per_date()
    ON CONFLICT (company_id, trade_date, is_current) DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        adjusted_close_price = EXCLUDED.adjusted_close_price,
        volume = EXCLUDED.volume,
        end_date = EXCLUDED.end_date;
    
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count;
END;
$$ LANGUAGE plpgsql;

-- Additional indexes for performance
CREATE INDEX idx_companies_ticker ON companies(ticker_symbol);
CREATE INDEX idx_financial_statements_company_type ON financial_statements(company_id, statement_type);
CREATE INDEX idx_ingestion_errors_component ON ingestion_errors(component_name, created_at DESC);
CREATE INDEX idx_performance_metrics_component ON performance_metrics(component_name, timestamp DESC);

-- Comments for clarity
COMMENT ON TABLE stock_prices_realtime IS 'Stores multiple real-time price records per company with surrogate primary key';
COMMENT ON COLUMN stock_prices_realtime.realtime_id IS 'Auto-incrementing surrogate primary key';
COMMENT ON COLUMN stock_prices_realtime.current_price IS 'Current/latest price (NOT close_price)';
COMMENT ON TABLE stock_prices_historical IS 'Stores historical daily price data with close_price column';
COMMENT ON FUNCTION get_latest_realtime_per_date() IS 'Returns latest real-time data per company per date, mapping current_price to close_price';
COMMENT ON FUNCTION migrate_realtime_to_historical() IS 'Migrates latest real-time data to historical table';
