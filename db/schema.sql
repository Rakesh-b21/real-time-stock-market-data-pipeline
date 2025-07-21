-- Table for stock price data
CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    current_price DECIMAL(10, 4) NOT NULL,
    open_price DECIMAL(10, 4),
    high_price DECIMAL(10, 4),
    low_price DECIMAL(10, 4),
    volume BIGINT,
    timestamp TIMESTAMPTZ NOT NULL,
    ingestion_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_timestamp ON stock_prices (symbol, timestamp DESC);

-- Table for ticker metadata
CREATE TABLE IF NOT EXISTS tickers (
    symbol VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Table for ingestion errors
CREATE TABLE IF NOT EXISTS ingestion_errors (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10),
    error_message TEXT,
    error_time TIMESTAMPTZ DEFAULT NOW()
); 