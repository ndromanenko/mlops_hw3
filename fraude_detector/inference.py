import os
import shutil
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier

from logger_config import get_logger
from preprocessing import build_features

BUNDLED_MODEL = Path(__file__).parent / "models" / "catboost_fraud.cbm"
MODELS_DIR = Path(os.getenv("MODELS_DIR", "/artifacts/models"))
LATEST_POINTER = MODELS_DIR / "latest.txt"
INITIAL_VERSION = "initial"
THRESHOLD = 0.95

log = get_logger("fraud_detector")

_model = None
_version = None


def model_path(version):
    return MODELS_DIR / f"model_{version}.cbm"


def ensure_bootstrap():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if read_latest_version():
        return
    initial = model_path(INITIAL_VERSION)
    if not initial.exists():
        shutil.copyfile(BUNDLED_MODEL, initial)
        log.info(f"Исходная модель скопирована в {initial}")
    tmp = MODELS_DIR / ".latest.tmp"
    tmp.write_text(INITIAL_VERSION + "\n", encoding="utf-8")
    os.replace(tmp, LATEST_POINTER)


def read_latest_version():
    try:
        return LATEST_POINTER.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def load_model(version):
    model = CatBoostClassifier()
    model.load_model(str(model_path(version)))
    return model


def current_model():
    global _model, _version
    version = read_latest_version()
    if version and version != _version:
        try:
            _model = load_model(version)
            _version = version
            log.info(f"Загружена модель версии {version}")
        except Exception:
            if _model is None:
                raise
            log.exception(f"Не удалось загрузить модель {version}, продолжаю на {_version}")
    if _model is None:
        raise RuntimeError(f"Нет опубликованной модели в {MODELS_DIR}")
    return _model, _version


def predict(data, threshold=THRESHOLD):
    model, version = current_model()
    X = build_features(data)
    score = model.predict_proba(X)[:, 1]
    return pd.DataFrame({
        "score": score,
        "fraud_flag": (score >= threshold).astype(int),
        "model_version": version,
    })
