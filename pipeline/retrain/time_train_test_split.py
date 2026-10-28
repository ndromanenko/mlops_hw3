import logging
from pathlib import Path

import pandas as pd

from pipeline.settings import LABEL, VALID_FRACTION

logger = logging.getLogger(__name__)


def time_train_test_split(window_info: dict) -> dict:
    """Делит окно по времени: ранние месяцы в обучение, самый свежий месяц в test."""
    run_dir = Path(window_info["run_dir"])
    frame = pd.read_parquet(window_info["window_path"]).sort_values("transaction_time", kind="stable")
    periods = frame["transaction_time"].dt.to_period("M")
    test_month = periods.max()
    history = frame[periods < test_month]
    test = frame[periods == test_month]
    n_valid = int(len(history) * VALID_FRACTION)
    train, valid = history.iloc[:-n_valid], history.iloc[-n_valid:]

    for name, part in (("train", train), ("valid", valid), ("test", test)):
        if part[LABEL].nunique() < 2:
            raise RuntimeError(f"В {name} нет обоих классов: {len(part)} строк, фрод {part[LABEL].sum()}")
        part.to_parquet(run_dir / f"{name}_raw.parquet", index=False)

    train_months = sorted(str(p) for p in periods[periods < test_month].unique())
    logger.info(
        "train %s: %s строк, valid %s строк, test %s: %s строк",
        train_months, len(train), len(valid), test_month, len(test),
    )
    return {
        **window_info,
        "train_months": train_months,
        "test_month": str(test_month),
        "rows": {"train": len(train), "valid": len(valid), "test": len(test)},
    }
