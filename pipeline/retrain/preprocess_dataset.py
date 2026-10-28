import logging
from pathlib import Path

import pandas as pd
from preprocessing import build_features

from pipeline.settings import LABEL

logger = logging.getLogger(__name__)


def preprocess_dataset(split_info: dict) -> dict:
    """Строит признаки для train, valid и test функцией build_features из fraude_detector."""
    run_dir = Path(split_info["run_dir"])
    for name in ("train", "valid", "test"):
        raw = pd.read_parquet(run_dir / f"{name}_raw.parquet")
        features = build_features(raw)
        features[LABEL] = raw[LABEL].to_numpy()
        features.to_parquet(run_dir / f"{name}_proc.parquet", index=False)
        logger.info("%s: %s", name, features.shape)
    return split_info
