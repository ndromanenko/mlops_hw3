import os
from pathlib import Path

from db import connect, ensure_schema, ensure_state, ensure_time_index, load_csv, row_count
from logger_config import get_logger, setup_logger

CSV_PATH = Path(os.getenv("LABELED_CSV_PATH", "/data/train.csv"))
INITIAL_NEXT_BATCH = os.getenv("INITIAL_NEXT_BATCH", "2019-04-01")

log = get_logger("data_loader")


def main():
    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            ensure_schema(cur)
            if row_count(cur) == 0:
                rows = load_csv(cur, CSV_PATH)
                log.info(f"В labeled_transactions загружено {rows} строк из {CSV_PATH}")
            else:
                log.info("Витрина labeled_transactions уже заполнена, повторная загрузка пропущена")
            ensure_time_index(cur)
            ensure_state(cur, INITIAL_NEXT_BATCH)
    finally:
        conn.close()
    log.info(f"Загрузка витрины завершена. Первый батч обучения: {INITIAL_NEXT_BATCH}")


if __name__ == "__main__":
    setup_logger()
    main()
