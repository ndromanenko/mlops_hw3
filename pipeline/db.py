import io
import logging
import os
from datetime import date

import pandas as pd
import psycopg2
from dateutil.relativedelta import relativedelta


logger = logging.getLogger(__name__)

LABELED_COLUMNS = [
    "transaction_time", "merch", "cat_id", "amount", "name_1", "name_2",
    "gender", "street", "one_city", "us_state", "post_code", "lat", "lon",
    "population_city", "jobs", "merchant_lat", "merchant_lon", "target",
]


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def month_end_exclusive(month_start: date) -> date:
    return month_start + relativedelta(months=1)


def read_training_state(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT next_batch_month FROM training_state WHERE id = 1")
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Таблица training_state пуста. Сначала должен отработать data_loader.")
    return {"next_batch_month": row[0]}


def advance_training_state(conn, batch_month: date) -> bool:
    next_batch = month_end_exclusive(batch_month)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE training_state
            SET next_batch_month = %s, updated_at = now()
            WHERE id = 1 AND next_batch_month = %s
            """,
            (next_batch, batch_month),
        )
        advanced = cur.rowcount == 1
    conn.commit()
    if advanced:
        logger.info("Указатель сдвинут: %s -> %s", batch_month, next_batch)
    else:
        logger.info("Указатель уже не равен %s, повторно не сдвигаем.", batch_month)
    return advanced


def read_labeled_months(conn, start: date, end_exclusive: date) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {", ".join(LABELED_COLUMNS)}
            FROM labeled_transactions
            WHERE transaction_time >= %s AND transaction_time < %s
            ORDER BY transaction_time
            """,
            (start, end_exclusive),
        )
        frame = pd.DataFrame(cur.fetchall(), columns=LABELED_COLUMNS)
    frame["transaction_time"] = pd.to_datetime(frame["transaction_time"])
    return frame


def copy_labeled_frame(conn, frame: pd.DataFrame) -> int:
    buffer = io.StringIO()
    frame.loc[:, LABELED_COLUMNS].to_csv(
        buffer, index=False, header=False, date_format="%Y-%m-%d %H:%M:%S"
    )
    buffer.seek(0)
    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY labeled_transactions ({', '.join(LABELED_COLUMNS)}) FROM STDIN WITH (FORMAT CSV)",
            buffer,
        )
    return len(frame)
