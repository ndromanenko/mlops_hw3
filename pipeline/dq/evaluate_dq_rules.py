import json
import logging
from pathlib import Path

import pandas as pd

from pipeline.db import LABELED_COLUMNS

logger = logging.getLogger(__name__)

MIN_MONTH_ROWS = 10_000


def rule(rule_id: str, name: str, threshold: str, actual: str, passed: bool, details: list[str] | None = None) -> dict:
    return {"id": rule_id, "name": name, "threshold": threshold, "actual": actual, "passed": passed, "details": details or []}


def check_nulls(profile: dict) -> dict:
    counters = profile["counters"]
    nulls = {c: counters[f"null_{c}"] for c in LABELED_COLUMNS if counters[f"null_{c}"]}
    return rule("DQ1", "Полнота: нет NULL ни в одной колонке", "0 NULL",
                f"{sum(nulls.values())} NULL", not nulls, [f"{c}: {n}" for c, n in nulls.items()])


def check_target(profile: dict) -> dict:
    bad = profile["counters"]["bad_target"]
    return rule("DQ2", "Разметка: target только 0 или 1", "0 нарушений", f"{bad} нарушений", bad == 0)


def check_amount(profile: dict) -> dict:
    bad = profile["counters"]["bad_amount"]
    return rule("DQ3", "Сумма транзакции положительная и правдоподобная", f"0 < amount < {profile['max_amount']:,}",
                f"{bad} нарушений", bad == 0)


def check_duplicates(profile: dict) -> dict:
    dups = profile["duplicates"]
    return rule("DQ4", "Уникальность: нет полных дублей строк", "0 дублей", f"{dups} дублей", dups == 0)


def check_months(months: pd.DataFrame) -> dict:
    periods = pd.PeriodIndex(months["month"], freq="M")
    gaps = sorted(map(str, set(pd.period_range(periods.min(), periods.max(), freq="M")) - set(periods)))
    small = months[months["rows"] < MIN_MONTH_ROWS]
    details = [f"нет месяца {g}" for g in gaps] + [f"{r.month}: {r.rows} строк" for r in small.itertuples()]
    return rule("DQ5", "Месяцы: каждый заполнен, пропусков нет",
                f">= {MIN_MONTH_ROWS:,} строк в месяце, 0 пропущенных месяцев",
                f"минимум {months['rows'].min():,} строк, пропусков {len(gaps)}", not details, details)


def evaluate_dq_rules(profile_info: dict) -> dict:
    """Применяет 5 правил DQ к профилю витрины."""
    profile = json.loads(Path(profile_info["profile_path"]).read_text(encoding="utf-8"))
    months = pd.DataFrame(profile["months"])
    months["fraud_rate"] = months["frauds"] / months["rows"]
    results = [
        check_nulls(profile),
        check_target(profile),
        check_amount(profile),
        check_duplicates(profile),
        check_months(months),
    ]
    failed = [r["id"] for r in results if not r["passed"]]
    for r in results:
        logger.info("%s %s: %s (%s)", "PASS" if r["passed"] else "FAIL", r["id"], r["name"], r["actual"])

    results_path = Path(profile_info["run_dir"]) / "results.json"
    payload = {
        "collected_at": profile["collected_at"],
        "total_rows": profile["counters"]["total_rows"],
        "rules": results,
        "failed": failed,
        "months": months.to_dict(orient="records"),
    }
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**profile_info, "results_path": str(results_path), "failed": failed}
