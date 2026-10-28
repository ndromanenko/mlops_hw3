import hashlib
import json
import logging
import os
from datetime import date
from pathlib import Path

from pipeline.settings import HISTORY_FILE, LATEST_POINTER, MODELS_DIR, REJECTED_DIR

logger = logging.getLogger(__name__)


def make_version(batch_month: date, run_id: str) -> str:
    return f"{batch_month:%Y%m}_{hashlib.sha1(run_id.encode()).hexdigest()[:8]}"


def model_path(version: str) -> Path:
    return MODELS_DIR / f"model_{version}.cbm"


def metrics_path(version: str, rejected: bool = False) -> Path:
    return (REJECTED_DIR if rejected else MODELS_DIR) / f"model_{version}.json"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, default=str))


def save_model(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    model.save_model(str(tmp))
    os.replace(tmp, path)


def load_model(path: Path):
    from catboost import CatBoostClassifier

    model = CatBoostClassifier()
    model.load_model(str(path))
    return model


def move_artifact(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
    elif not dst.exists():
        raise FileNotFoundError(f"Нет ни {src}, ни {dst}")


def read_latest_version() -> str | None:
    try:
        return LATEST_POINTER.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def set_latest_version(version: str) -> None:
    atomic_write_text(LATEST_POINTER, version + "\n")
    logger.info("latest.txt -> %s", version)


def append_history(record: dict) -> None:
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            if json.loads(line).get("version") == record["version"]:
                return
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
