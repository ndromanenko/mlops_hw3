import logging
import shutil
from pathlib import Path

from pipeline.registry import atomic_write_text
from pipeline.settings import DQ_REPORTS_DIR

logger = logging.getLogger(__name__)


def publish_dq_report(report_info: dict) -> str:
    """Кладёт отчёт в artifacts/dq_reports и обновляет latest.html."""
    stem = f"dq_{report_info['collected_at']}"
    html = Path(report_info["report_path"]).read_text(encoding="utf-8")
    results = Path(report_info["results_path"]).read_text(encoding="utf-8")
    for name, text in ((f"{stem}.html", html), (f"{stem}.json", results), ("latest.html", html), ("latest.json", results)):
        atomic_write_text(DQ_REPORTS_DIR / name, text)
    shutil.rmtree(report_info["run_dir"], ignore_errors=True)
    report = DQ_REPORTS_DIR / f"{stem}.html"
    logger.info("Отчёт опубликован: %s, не пройдено: %s", report, report_info["failed"] or "нет")
    return str(report)
