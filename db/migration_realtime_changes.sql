-- Migration Script: Update Real-time Data Storage for Multiple Records
-- This script modifies the stock_prices_realtime table to allow multiple records
-- per company_id and trade_datetime combination

-- Step 1: Drop the existing primary key constraint on company_id
ALTER TABLE stock_prices_realtime DROP CONSTRAINT stock_prices_realtime_pkey;

-- Step 2: Add a surrogate primary key (auto-incrementing ID)
ALTER TABLE stock_prices_realtime ADD COLUMN realtime_id BIGSERIAL PRIMARY KEY;

-- Step 3: Add an index for efficient querying by company_id and trade_datetime
CREATE INDEX idx_stock_prices_realtime_company_datetime ON stock_prices_realtime(company_id, trade_datetime DESC);

-- Step 4: Add an index for getting latest records per company
CREATE INDEX idx_stock_prices_realtime_latest ON stock_prices_realtime(company_id, last_updated DESC);

-- Step 5: Update historical table schema to remove start_date requirement
-- (Optional - only if you want to simplify historical data structure)
ALTER TABLE stock_prices_historical ALTER COLUMN start_date DROP NOT NULL;

-- Step 6: Create a function to get latest real-time data per company per date
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
        rt.current_price as close_price,
        rt.volume,
        rt.trade_datetime
    FROM stock_prices_realtime rt
    JOIN companies c ON rt.company_id = c.company_id
    ORDER BY rt.company_id, DATE(rt.trade_datetime), rt.trade_datetime DESC;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create a function to migrate real-time data to historical
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
        trade_date as start_date, -- Use trade_date as start_date
        NULL as end_date, -- NULL indicates current/latest
        TRUE as is_current
    FROM get_latest_realtime_per_date()
    ON CONFLICT (company_id, trade_date, start_date) DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        adjusted_close_price = EXCLUDED.adjusted_close_price,
        volume = EXCLUDED.volume,
        end_date = EXCLUDED.end_date,
        is_current = EXCLUDED.is_current;
    
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Create indexes for better performance with multiple records
CREATE INDEX idx_stock_prices_realtime_company_id ON stock_prices_realtime(company_id);
CREATE INDEX idx_stock_prices_realtime_trade_datetime ON stock_prices_realtime(trade_datetime DESC);

-- Step 9: Add a trigger to automatically update last_updated timestamp
CREATE OR REPLACE FUNCTION update_realtime_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_realtime_timestamp
    BEFORE INSERT ON stock_prices_realtime
    FOR EACH ROW
    EXECUTE FUNCTION update_realtime_timestamp();

-- Verification queries (run these to verify the changes)
-- SELECT COUNT(*) FROM stock_prices_realtime;
-- SELECT * FROM get_latest_realtime_per_date() LIMIT 5;
-- SELECT migrate_realtime_to_historical();
