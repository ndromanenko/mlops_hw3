import logging
from datetime import date

import pandas as pd

from pipeline.db import copy_labeled_frame, get_conn, month_end_exclusive

logger = logging.getLogger(__name__)


def append_labeled_batch(batch_info: dict) -> dict:
    """Записывает батч месяца batch_month в labeled_transactions."""
    month_start = date.fromisoformat(batch_info["batch_month"])
    frame = pd.read_parquet(batch_info["batch_path"])
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM labeled_transactions WHERE transaction_time >= %s AND transaction_time < %s",
                    (month_start, month_end_exclusive(month_start)),
                )
                replaced = cur.rowcount
            written = copy_labeled_frame(conn, frame)
    finally:
        conn.close()
    logger.info("Месяц %s: записано %s строк, заменено старых %s", month_start, written, replaced)
    return {**batch_info, "written_rows": written}
