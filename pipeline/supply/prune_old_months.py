import logging
import shutil
from pathlib import Path

from dateutil.relativedelta import relativedelta

from pipeline.db import get_conn, read_training_state
from pipeline.settings import HISTORY_MONTHS, WINDOW_MONTHS

logger = logging.getLogger(__name__)


def prune_old_months(batch_info: dict) -> dict:
    """Удаляет из labeled_transactions строки старше HISTORY_MONTHS месяцев."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT date_trunc('month', max(transaction_time))::date FROM labeled_transactions")
                newest_month = cur.fetchone()[0]
                window_start = read_training_state(conn)["next_batch_month"] - relativedelta(months=WINDOW_MONTHS - 1)
                cutoff = min(newest_month - relativedelta(months=HISTORY_MONTHS - 1), window_start)
                cur.execute("DELETE FROM labeled_transactions WHERE transaction_time < %s", (cutoff,))
                deleted = cur.rowcount
    finally:
        conn.close()
    shutil.rmtree(Path(batch_info["batch_path"]).parent, ignore_errors=True)
    logger.info("Самый новый месяц %s, граница хранения %s, удалено строк: %s", newest_month, cutoff, deleted)
    return {"batch_month": batch_info["batch_month"], "cutoff": cutoff.isoformat(), "deleted_rows": deleted}
