# Real-time Stock Market Data Pipeline

A real-time pipeline for ingesting, streaming, and persisting stock market data using Python, Kafka, and PostgreSQL.

## System Design Diagram

A full system design diagram (PlantUML) is available in `docs/system_design.puml`.

To view the diagram:
- Use an online PlantUML editor (e.g., https://www.planttext.com/)
- Or use a PlantUML plugin in your IDE

The diagram covers:
- Data ingestion from Yahoo Finance
- Streaming via Kafka
- Persistence in PostgreSQL
- Real-time analytics and ML predictions
- Visualization with Dash/Plotly dashboard

## Features
- Fetches live stock data from Yahoo Finance (configurable tickers)
- Streams data to Kafka topic (`stock_market_data`)
- Consumes data and stores it in PostgreSQL
- Docker Compose setup for Kafka, Zookeeper, PostgreSQL, and Adminer

## Local Setup

### Prerequisites
- **PostgreSQL 17.5**: [Download](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
- **Kafka 3.9.1**: [Download](https://kafka.apache.org/downloads)

### Kafka Setup Notes
- Update `zookeeper.properties` and `server.properties` to set data/log directories to your local Kafka path (replace any `tmp` paths).
- On **Windows 11**:
  - Edit `zookeeper-server-start.bat`.
  - Comment out the block:
    ```bat
    IF ["%KAFKA_HEAP_OPTS%"] EQU [""] ...
    ```
  - Below it, add:
    ```bat
    IF ["%KAFKA_HEAP_OPTS%"] EQU [""] (
        rem Default heap size for Kafka
        set KAFKA_HEAP_OPTS=-Xmx1G -Xms1G
    )
    ```

### Quick Start

1. **Clone the repository**
    ```sh
    git clone <repo-url>
    cd real-time-stock-market-data-pipeline
    ```
2. **Start Infrastructure**
    ```sh
    docker-compose up -d
    ```
3. **Initialize Database**
    ```sh
    docker exec -i <postgres_container_name> psql -U postgres -d stocks < db/schema.sql
    ```
4. **Install Python Dependencies**
    ```sh
    pip install -r requirements.txt
    ```
5. **Run Producer**
    ```sh
    python producer/producer.py
    ```
6. **Run Consumer**
    ```sh
    python consumer/consumer.py
    ```

## Configuration
- Edit `producer/config.py` for tickers and polling interval.
- Environment variables can override Kafka/Postgres connection settings.

## Table Schema
See `db/schema.sql` for details.

## Notes
- Use Adminer at [http://localhost:8080](http://localhost:8080) to view the database.
- For production, consider adding authentication, monitoring, and scaling strategies.

---

## Acknowledgments
Created with a lot of backtracking, research, and with the help of our lovely pair programmer Cursor, plus debugging help from Copilot and Gemini. 