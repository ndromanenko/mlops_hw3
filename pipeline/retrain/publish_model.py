import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.registry import append_history, metrics_path, model_path, move_artifact, set_latest_version, write_json

logger = logging.getLogger(__name__)

RECORD_KEYS = (
    "version", "decision", "reason", "batch_month", "window_start", "train_months", "test_month",
    "rows", "candidate_metrics", "champion_version", "champion_metrics",
)


def build_record(evaluation: dict) -> dict:
    return {key: evaluation[key] for key in RECORD_KEYS} | {
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def publish_model(evaluation: dict) -> str:
    """Кладёт кандидата в общий каталог и переключает на него прод."""
    version = evaluation["version"]
    move_artifact(Path(evaluation["candidate_path"]), model_path(version))
    record = build_record(evaluation)
    write_json(metrics_path(version), record)
    set_latest_version(version)
    append_history(record)
    logger.info("Опубликована модель %s: %s", version, evaluation["reason"])
    return version


def reject_model(evaluation: dict) -> str:
    """Сохраняет метрики отклонённого кандидата в models/rejected, прод не меняет."""
    version = evaluation["version"]
    record = build_record(evaluation)
    write_json(metrics_path(version, rejected=True), record)
    Path(evaluation["candidate_path"]).unlink(missing_ok=True)
    append_history(record)
    logger.info("Модель %s отклонена: %s", version, evaluation["reason"])
    return version
