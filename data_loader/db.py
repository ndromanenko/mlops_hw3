import os

import psycopg2


COLUMNS = [
    "transaction_time", "merch", "cat_id", "amount", "name_1", "name_2",
    "gender", "street", "one_city", "us_state", "post_code", "lat", "lon",
    "population_city", "jobs", "merchant_lat", "merchant_lon", "target",
]

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS labeled_transactions (
    transaction_time TIMESTAMP NOT NULL,
    merch TEXT,
    cat_id TEXT,
    amount DOUBLE PRECISION,
    name_1 TEXT,
    name_2 TEXT,
    gender TEXT,
    street TEXT,
    one_city TEXT,
    us_state TEXT,
    post_code INTEGER,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    population_city INTEGER,
    jobs TEXT,
    merchant_lat DOUBLE PRECISION,
    merchant_lon DOUBLE PRECISION,
    target SMALLINT
);

CREATE TABLE IF NOT EXISTS training_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    next_batch_month DATE NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

CREATE_TIME_INDEX = """
CREATE INDEX IF NOT EXISTS labeled_transactions_time_idx
ON labeled_transactions (transaction_time);
"""

INSERT_INITIAL_STATE = """
INSERT INTO training_state (id, next_batch_month)
VALUES (1, %s)
ON CONFLICT (id) DO NOTHING;
"""


def get_db_config():
    return {
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "user": os.getenv("POSTGRES_USER", "postgres_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres_password"),
        "dbname": os.getenv("POSTGRES_DB", "postgres_db"),
    }


def connect():
    return psycopg2.connect(**get_db_config())


def ensure_schema(cur):
    cur.execute(CREATE_TABLES)


def row_count(cur):
    cur.execute("SELECT COUNT(*) FROM labeled_transactions;")
    return cur.fetchone()[0]


def load_csv(cur, path):
    with path.open(encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        if header != COLUMNS:
            raise ValueError(f"Колонки {path} не совпадают с витриной: {header}")
        cur.copy_expert(
            f"COPY labeled_transactions ({', '.join(COLUMNS)}) FROM STDIN WITH (FORMAT CSV)",
            f,
        )
    return cur.rowcount


def ensure_time_index(cur):
    cur.execute(CREATE_TIME_INDEX)


def ensure_state(cur, next_batch_month):
    cur.execute(INSERT_INITIAL_STATE, (next_batch_month,))
