import calendar
import logging
from datetime import date

import pandas as pd

from pipeline.db import LABELED_COLUMNS, get_conn
from pipeline.settings import SAMPLE_SIZE, run_work_dir

logger = logging.getLogger(__name__)


def next_month_start(max_time) -> date:
    return (pd.Timestamp(max_time).to_period("M") + 1).to_timestamp().date()


def shift_into_month(frame: pd.DataFrame, month_start: date) -> pd.DataFrame:
    """Переносит transaction_time в month_start, сохраняя день, час и минуту."""
    shifted = frame.copy()
    times = pd.to_datetime(shifted["transaction_time"])
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    shifted["transaction_time"] = pd.to_datetime({
        "year": month_start.year,
        "month": month_start.month,
        "day": times.dt.day.clip(upper=last_day),
        "hour": times.dt.hour,
        "minute": times.dt.minute,
    })
    return shifted


def sample_next_month(run_id: str) -> dict:
    """Собирает батч следующего месяца из случайных строк витрины."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT max(transaction_time) FROM labeled_transactions")
            max_time = cur.fetchone()[0]
            if max_time is None:
                raise RuntimeError("Витрина labeled_transactions пуста. Сначала должен отработать data_loader.")
            cur.execute(
                f"SELECT {', '.join(LABELED_COLUMNS)} FROM labeled_transactions ORDER BY random() LIMIT %s",
                (SAMPLE_SIZE,),
            )
            frame = pd.DataFrame(cur.fetchall(), columns=LABELED_COLUMNS)
    finally:
        conn.close()

    month_start = next_month_start(max_time)
    batch = shift_into_month(frame, month_start).drop_duplicates()
    run_dir = run_work_dir("supply", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    batch_path = run_dir / "batch.parquet"
    batch.to_parquet(batch_path, index=False)
    logger.info("Батч %s: %s строк, фрод %.3f%%", month_start, len(batch), 100 * batch["target"].mean())
    return {"batch_path": str(batch_path), "batch_month": month_start.isoformat(), "rows": len(batch)}
