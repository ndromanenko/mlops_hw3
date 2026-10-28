import shutil
from datetime import date

from pipeline.db import advance_training_state, get_conn
from pipeline.registry import metrics_path, model_path


def advance_training_pointer(evaluation: dict) -> dict:
    """Сдвигает next_batch_month на следующий месяц и удаляет рабочий каталог прогона."""
    version = evaluation["version"]
    published = evaluation["decision"] == "published"
    saved = model_path(version) if published else metrics_path(version, rejected=True)
    if not saved.exists():
        raise FileNotFoundError(f"Нет {saved}: результат прогона не сохранён, указатель не сдвигаем")

    batch_month = date.fromisoformat(evaluation["batch_month"])
    conn = get_conn()
    try:
        advanced = advance_training_state(conn, batch_month)
    finally:
        conn.close()
    shutil.rmtree(evaluation["run_dir"], ignore_errors=True)
    return {"version": version, "decision": evaluation["decision"], "batch_month": batch_month.isoformat(), "advanced": advanced}
