import logging
from datetime import date
from pathlib import Path

import pandas as pd
from preprocessing import CAT_FEATURES

from pipeline.registry import make_version, save_model
from pipeline.settings import LABEL

logger = logging.getLogger(__name__)


def split_xy(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    return frame.drop(columns=[LABEL]), frame[LABEL]


def fit_catboost(preproc_info: dict) -> dict:
    """Обучает кандидата на train с early stopping по valid."""
    from catboost import CatBoostClassifier

    run_dir = Path(preproc_info["run_dir"])
    x_train, y_train = split_xy(pd.read_parquet(run_dir / "train_proc.parquet"))
    x_valid, y_valid = split_xy(pd.read_parquet(run_dir / "valid_proc.parquet"))

    model = CatBoostClassifier(
        iterations=300,
        learning_rate=0.1,
        depth=5,
        l2_leaf_reg=3.0,
        loss_function="Logloss",
        eval_metric="PRAUC",
        auto_class_weights="Balanced",
        early_stopping_rounds=50,
        random_seed=42,
        task_type="CPU",
        allow_writing_files=False,
        verbose=50,
    )
    model.fit(x_train, y_train, cat_features=CAT_FEATURES, eval_set=(x_valid, y_valid), use_best_model=True)

    version = make_version(date.fromisoformat(preproc_info["batch_month"]), preproc_info["run_id"])
    candidate_path = run_dir / "candidate.cbm"
    save_model(model, candidate_path)
    logger.info("Кандидат %s: лучшая итерация %s, сохранён в %s", version, model.get_best_iteration(), candidate_path)
    return {**preproc_info, "version": version, "candidate_path": str(candidate_path)}
