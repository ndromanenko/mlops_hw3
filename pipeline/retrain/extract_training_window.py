import logging

import pandas as pd
from airflow.exceptions import AirflowSkipException
from dateutil.relativedelta import relativedelta

from pipeline.db import get_conn, month_end_exclusive, read_labeled_months, read_training_state
from pipeline.settings import WINDOW_MONTHS, run_work_dir

logger = logging.getLogger(__name__)


def extract_training_window(run_id: str) -> dict:
    """Собирает окно из WINDOW_MONTHS месяцев, которое заканчивается next_batch_month."""
    conn = get_conn()
    try:
        batch_month = read_training_state(conn)["next_batch_month"]
        window_start = batch_month - relativedelta(months=WINDOW_MONTHS - 1)
        frame = read_labeled_months(conn, window_start, month_end_exclusive(batch_month))
    finally:
        conn.close()

    months = set(frame["transaction_time"].dt.to_period("M").unique())
    if pd.Period(batch_month, "M") not in months:
        raise AirflowSkipException(f"В витрине нет месяца {batch_month}: его ещё не поставили.")
    missing = set(pd.period_range(window_start, batch_month, freq="M")) - months
    if missing:
        raise RuntimeError(f"В окне {window_start} - {batch_month} нет месяцев {sorted(map(str, missing))}")

    run_dir = run_work_dir("retrain", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    window_path = run_dir / "window.parquet"
    frame.to_parquet(window_path, index=False)
    logger.info("Окно %s - %s: %s строк", window_start, batch_month, len(frame))
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "window_path": str(window_path),
        "window_start": window_start.isoformat(),
        "batch_month": batch_month.isoformat(),
    }
