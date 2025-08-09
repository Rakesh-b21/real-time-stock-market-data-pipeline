# Error Log & Fixes Documentation

## 1. ModuleNotFoundError: No module named 'producer.config'; 'producer' is not a package
**Cause:** Running `python producer/producer.py` directly, which does not treat `producer` as a package.
**Fix:**
- Add `__init__.py` to `producer/` and `consumer/` directories.
- Run as a module from the project root:
  ```sh
  python -m producer.producer
  python -m consumer.consumer
  ```

---

## 2. Environment Variables from `.env` Not Loaded
**Cause:** Python does not load `.env` automatically.
**Fix:**
- Install `python-dotenv` and add to `requirements.txt`.
- Add to the top of each script:
  ```python
  from dotenv import load_dotenv
  load_dotenv()
  ```

---

## 3. Kafka/Database Not Running Before Pipeline
**Cause:** Running the pipeline before starting Kafka, Zookeeper, or PostgreSQL.
**Fix:**
- Always start Kafka, Zookeeper, and PostgreSQL before running the pipeline.

---

## 4. Numpy Type Error: `schema "np" does not exist`
**Error Example:**
```
ERROR:__main__:Error inserting analytics data for TSLA: schema "np" does not exist
LINE 11: np.float64(0.6887045608958573), np.f...
```
**Cause:** Passing numpy types (e.g., `np.float64`) directly to PostgreSQL.
**Fix:** Convert all numpy types to Python native types using `float()` before inserting into the database.

---

## 5. Unsupported Format String Passed to NoneType
**Error Example:**
```
ERROR:__main__:Failed to process message: unsupported format string passed to NoneType.__format__
```
**Cause:** Logging code tried to format `None` as a float (e.g., `f"{value:.2f}"` when `value` is `None`).
**Fix:** Add null checks before formatting:
```python
rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "N/A"
```

---

## 6. Analytics Consumer Does Not Stop After N Messages
**Cause:** `MAX_MESSAGES` was not implemented in the analytics consumer.
**Fix:** Add `MAX_MESSAGES` environment variable and check in the analytics consumer's main loop:
```python
if MAX_MESSAGES > 0 and self.messages_processed >= MAX_MESSAGES:
    break
```

---

## 7. Kafka Topic Creation
**Cause:** Topic not created when running Kafka locally (auto-creation may be disabled).
**Fix:** Manually create the topic:
```sh
bin/kafka-topics.sh --create --topic stock_market_data --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

---

## 8. Database Name Change Not Reflected
**Cause:** Changing the database name in only one place (e.g., `.env` but not `docker-compose.yml` or vice versa).
**Fix:** Update the database name in all relevant places: `.env`, `docker-compose.yml`, and any scripts.

---

## 9. PowerShell Visualization Issues
**Cause:** Not using the correct Kafka console consumer command or missing Kafka tools in PATH.
**Fix:** Use the correct command and ensure Kafka's `bin` directory is in your PATH:
```powershell
kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic stock_market_data --from-beginning
```

---

## 10. Enhanced Schema Database Errors
**Error Examples:**
```
ERROR: relation "stock_prices" does not exist
ERROR: column "symbol" does not exist
ERROR: column "company_id" does not exist
```
**Cause:** Using old schema references after migrating to enhanced schema.
**Fix:**
- Ensure enhanced schema is properly initialized: `psql -U postgres -d stocks -f db/enhanced_schema.sql`
- Update all component queries to use new table names:
  - `stock_prices` → `stock_prices_realtime` and `stock_prices_historical`
  - `symbol` → `ticker_symbol` and `company_id`
- Use company manager for company data operations
- Update dashboard queries to join with companies table

---

## 11. Company Data Not Found
**Error Examples:**
```
ERROR: company_id not found for ticker_symbol
ERROR: No companies found in database
```
**Cause:** Companies not initialized in the enhanced schema.
**Fix:**
- Ensure the enhanced producer runs first to initialize companies
- Check that `utils/company_manager.py` is working correctly
- Verify that companies are being created in the `companies` table
- Run producer with `_initialize_companies()` method

---

## 12. Dashboard Shows No Data
**Cause:** Dashboard queries not updated for new schema structure.
**Fix:**
- Update dashboard queries to use new table names and joins
- Ensure proper joins between `stock_prices_realtime` and `companies` tables
- Check that `get_available_tickers()` function works with new schema
- Verify time window queries use correct timestamp columns

---

## 13. JSONB Dictionary Conversion Error
**Error Examples:**
```
ERROR:utils.company_manager - Error in get_or_create_company: can't adapt type 'dict'
ERROR:utils.company_manager - Failed to process AAPL: can't adapt type 'dict'
```
**Cause:** Trying to insert a Python dictionary directly into a PostgreSQL JSONB column without converting it to JSON string first.
**Fix:**
- Import `json` module in the company manager
- Convert the dictionary to JSON string before inserting: `json.dumps(company_info)`
- Update the INSERT statement to use the converted JSON string
- Ensure all environment variables match the expected names (POSTGRES_HOST, POSTGRES_DB, etc.)

---

## 14. Analytics Column Name Mismatch Error
**Error Examples:**
```
ERROR:__main__:Error inserting analytics data for AMZN: column "bollinger_upper" of relation "stock_analytics" does not exist
LINE 5:                         bollinger_upper, bollinger_lower, bo...
```
**Cause:** The analytics consumer is trying to insert data using column names that don't match the actual enhanced schema table structure.
**Fix:**
- Update analytics consumer INSERT statement to use correct column names:
  - `bollinger_upper` → `bb_upper`
  - `bollinger_lower` → `bb_lower` 
  - `bollinger_middle` → `bb_middle`
  - `macd_line` → `macd`
  - `volatility_20` → `volatility`
  - `price_change_pct` → `price_change_percent`
- Update dashboard queries to use correct column names
- Update chart creation functions to reference correct columns
- Ensure all components use the same column naming convention as the enhanced schema

---

## 15. Analytics Consumer Missing Company Manager
**Error Examples:**
```
ERROR:__main__:Error checking alerts for AMD: 'AnalyticsConsumer' object has no attribute 'company_manager'
```
**Cause:** The analytics consumer is trying to use `self.company_manager` but it's not initialized in the constructor.
**Fix:**
- Import the company manager in the analytics consumer
- Add `self.company_manager = company_manager` in the `__init__` method
- Ensure proper import path is set up for the utils module

---

## 16. Historical Data Duplicate Key Violation
**Error Examples:**
```
ERROR:__main__:Error storing historical data for AAPL: duplicate key value violates unique constraint "stock_prices_historical_company_id_trade_date_start_date_key"
DETAIL: Key (company_id, trade_date, start_date)=(dc0ffa9e-a2ea-4833-8c1a-8e3692429c32, 2025-08-05, 2025-08-05) already exists.
```
**Cause:** The enhanced producer is trying to insert multiple historical data records for the same date, violating the unique constraint on (company_id, trade_date, start_date).
**Fix:**
- Modify historical data storage to only insert once per date
- Add check to skip insertion if data already exists for that date
- Use `logger.debug()` to log when skipping duplicate dates
- Ensure SCD Type 2 logic only triggers when there are actual price changes

---

## 17. Dashboard Predictions Column Mismatch
**Error Examples:**
```
ERROR:dashboard.app:Error fetching predictions: Execution failed on sql '
            SELECT c.ticker_symbol, p.predicted_date, p.predicted_price, p.confidence_score,
                   p.prediction_horizon, p.created_at
            FROM predictions p
            JOIN companies c ON p.company_id = c.company_id
            WHERE p.created_at >= NOW() - INTERVAL '1 hour'
             ORDER BY p.created_at DESC LIMIT %s': column p.prediction_horizon does not exist
```
**Cause:** The dashboard and ML scripts are trying to query/insert a column `prediction_horizon` that doesn't exist in the `predictions` table schema. The actual column is `prediction_type`.
**Fix:**
- Update dashboard `fetch_predictions()` function to use `p.prediction_type` instead of `p.prediction_horizon`
- Update ML batch prediction script to use `prediction_type` instead of `prediction_horizon`
- Ensure all references to prediction columns match the enhanced schema

---

# Summary Table

| Error Message / Symptom                                 | Cause                                      | Fix / Solution                                                                 |
|--------------------------------------------------------|---------------------------------------------|--------------------------------------------------------------------------------|
| ModuleNotFoundError for package imports                | Not running as a module                     | Add `__init__.py`, use `python -m ...`                                         |
| Env vars not loaded                                    | `.env` not loaded automatically             | Use `python-dotenv` and `load_dotenv()`                                        |
| Pipeline fails to connect to Kafka/Postgres            | Services not started                        | Start Kafka, Zookeeper, and Postgres first                                     |
| schema "np" does not exist                           | Numpy types passed to DB                    | Convert to Python float with `float()`                                         |
| unsupported format string passed to NoneType.__format__| Formatting `None` as float in logs          | Null check before formatting, use `"N/A"`                                      |
| relation "stock_prices" does not exist                 | Using old schema after migration            | Initialize enhanced schema, update all queries                                 |
| company_id not found                                   | Companies not initialized                   | Run enhanced producer first, check company manager                             |
| Dashboard shows no data                                | Dashboard queries not updated               | Update queries for new schema, check joins and table names                     |
| can't adapt type 'dict'                                | Dictionary passed to JSONB column           | Convert dict to JSON string with `json.dumps()`                                |
| column "bollinger_upper" does not exist                | Column name mismatch in analytics           | Update column names to match enhanced schema                                   |
| 'AnalyticsConsumer' object has no attribute 'company_manager' | Missing company manager initialization      | Add company manager import and initialization in analytics consumer             |
| duplicate key value violates unique constraint         | Multiple historical data inserts per date   | Check for existing data before inserting, skip duplicates                      |
| column p.prediction_horizon does not exist             | Column name mismatch in predictions         | Update to use `prediction_type` instead of `prediction_horizon`                 | 