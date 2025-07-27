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
**Fix:** Add `MAX_MESSAGES` environment variable and check in the analytics consumer’s main loop:
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
**Fix:** Use the correct command and ensure Kafka’s `bin` directory is in your PATH:
```powershell
kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic stock_market_data --from-beginning
```

---

# Summary Table

| Error Message / Symptom                                 | Cause                                      | Fix / Solution                                                                 |
|--------------------------------------------------------|---------------------------------------------|--------------------------------------------------------------------------------|
| ModuleNotFoundError for package imports                | Not running as a module                     | Add `__init__.py`, use `python -m ...`                                         |
| Env vars not loaded                                    | `.env` not loaded automatically             | Use `python-dotenv` and `load_dotenv()`                                        |
| Pipeline fails to connect to Kafka/Postgres            | Services not started                        | Start Kafka, Zookeeper, and Postgres first                                     |
| schema "np" does not exist                           | Numpy types passed to DB                    | Convert to Python float with `float()`                                         |
| unsupported format string passed to NoneType.__format__| Formatting `None` as float in logs          | Null check before formatting, use `"N/A"`                                      |
| Analytics consumer runs forever                        | No message limit implemented                | Add `MAX_MESSAGES` logic in analytics consumer                                 |
| Kafka topic not found                                 | Topic not auto-created                      | Manually create topic with `kafka-topics.sh`                                   |
| Database name mismatch                                 | Not updated everywhere                      | Update `.env`, `docker-compose.yml`, and scripts                               |
| PowerShell Kafka monitor not working                   | Wrong command or missing tools              | Use correct command, ensure Kafka tools in PATH                                | 