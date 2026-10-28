import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def render_dq_report(results_info: dict) -> dict:
    """Собирает HTML-отчёт из results.json."""
    results = json.loads(Path(results_info["results_path"]).read_text(encoding="utf-8"))
    rules = pd.DataFrame(results["rules"])[["id", "name", "threshold", "actual", "passed"]]
    rules["passed"] = rules["passed"].map({True: "PASS", False: "FAIL"})
    months = pd.DataFrame(results["months"])

    html = (
        '<html><head><meta charset="utf-8"><title>DQ отчёт</title></head><body>'
        f"<h1>Data Quality: labeled_transactions</h1>"
        f"<p>Проверка {results['collected_at']}, строк в витрине: {results['total_rows']}</p>"
        f"<p>Не пройдено правил: {', '.join(results['failed']) or 'нет'}</p>"
        f"<h2>Правила</h2>{rules.to_html(index=False)}"
        f"<h2>Месяцы витрины</h2>{months.to_html(index=False)}"
        "</body></html>"
    )
    report_path = Path(results_info["run_dir"]) / "report.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info("Отчёт собран: %s", report_path)
    return {**results_info, "report_path": str(report_path)}
