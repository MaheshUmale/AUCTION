# QuestDB Database Scripts

This directory contains scripts to set up and interact with the QuestDB database for the auction trading bot.

## 1. `create_db.sql`

This script contains the `CREATE TABLE` statements required to set up the database schema. It will create all the necessary tables with the correct columns and data types.

### How to Use:

You can execute this script using the QuestDB web UI or any PostgreSQL-compatible client.

**Using `psql`:**

```bash
psql "user=admin password=quest host=localhost port=8812 dbname=auction_trading" -f create_db.sql
```

**Using the Web UI:**

1.  Navigate to the QuestDB web UI (usually `http://localhost:9000`).
2.  Copy the contents of `create_db.sql`.
3.  Paste the contents into the query editor.
4.  Click "Run".

## 2. `insert_samples.sql`

This script contains sample `INSERT` statements for each table. This is useful for populating the database with some initial data for testing and development.

### How to Use:

Similar to `create_db.sql`, you can execute this script using `psql` or the QuestDB web UI. Make sure you have already created the tables using `create_db.sql`.

**Using `psql`:**

```bash
psql "user=admin password=quest host=localhost port=8812 dbname=auction_trading" -f insert_samples.sql
```

## 3. Query UI (`../ui/query_ui.py`)

A simple Flask-based web interface to execute SQL queries against the QuestDB database and view the results in your browser.

### How to Run:

1.  Make sure you have the required Python packages installed:

    ```bash
    pip install Flask pandas psycopg2-binary
    ```

2.  Run the script from the root directory of the repository:

    ```bash
    python3 ui/query_ui.py
    ```

3.  Open your web browser and navigate to `http://127.0.0.1:5001`.
