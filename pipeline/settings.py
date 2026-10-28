import os
from pathlib import Path

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "/opt/airflow/artifacts"))
MODELS_DIR = ARTIFACTS_DIR / "models"
REJECTED_DIR = MODELS_DIR / "rejected"
DQ_REPORTS_DIR = ARTIFACTS_DIR / "dq_reports"
WORK_DIR = ARTIFACTS_DIR / "work"

LATEST_POINTER = MODELS_DIR / "latest.txt"
HISTORY_FILE = MODELS_DIR / "history.jsonl"
INITIAL_VERSION = "initial"

LABEL = "target"
WINDOW_MONTHS = int(os.getenv("WINDOW_MONTHS", "3"))
VALID_FRACTION = float(os.getenv("VALID_FRACTION", "0.2"))
FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", "0.95"))
METRIC_TOLERANCE = float(os.getenv("METRIC_TOLERANCE", "0.005"))

SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "50000"))
HISTORY_MONTHS = int(os.getenv("HISTORY_MONTHS", "24"))


def run_work_dir(dag: str, run_id: str) -> Path:
    return WORK_DIR / dag / run_id.replace(":", "_").replace("+", "_")
