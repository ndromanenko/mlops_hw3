import json
import logging
from datetime import datetime, timezone

from pipeline.db import LABELED_COLUMNS, get_conn
from pipeline.settings import run_work_dir

logger = logging.getLogger(__name__)

VIOLATIONS_SQL = f"""
SELECT
    COUNT(*) AS total_rows,
    {", ".join(f"COUNT(*) FILTER (WHERE {c} IS NULL) AS null_{c}" for c in LABELED_COLUMNS)},
    COUNT(*) FILTER (WHERE target NOT IN (0, 1)) AS bad_target,
    COUNT(*) FILTER (WHERE amount <= 0 OR amount >= %(max_amount)s) AS bad_amount
FROM labeled_transactions
"""

DUPLICATES_SQL = f"""
SELECT COALESCE(SUM(copies - 1), 0)
FROM (
    SELECT COUNT(*) AS copies
    FROM labeled_transactions
    GROUP BY {", ".join(LABELED_COLUMNS)}
    HAVING COUNT(*) > 1
) dups
"""

MONTHS_SQL = """
SELECT date_trunc('month', transaction_time)::date AS month, COUNT(*) AS rows, SUM(target) AS frauds
FROM labeled_transactions
GROUP BY 1
ORDER BY 1
"""

MAX_AMOUNT = 100_000


def collect_dataset_profile(run_id: str) -> dict:
    """Считает в Postgres агрегаты labeled_transactions, нужные правилам DQ."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(VIOLATIONS_SQL, {"max_amount": MAX_AMOUNT})
            counters = dict(zip([d[0] for d in cur.description], cur.fetchone()))
            cur.execute(DUPLICATES_SQL)
            duplicates = int(cur.fetchone()[0])
            cur.execute(MONTHS_SQL)
            months = [{"month": m.isoformat(), "rows": int(r), "frauds": int(f)} for m, r, f in cur.fetchall()]
    finally:
        conn.close()

    profile = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "counters": {k: int(v) for k, v in counters.items()},
        "duplicates": duplicates,
        "months": months,
        "max_amount": MAX_AMOUNT,
    }
    run_dir = run_work_dir("dq", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    profile_path = run_dir / "profile.json"
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Профиль витрины: %s строк, %s месяцев", profile["counters"]["total_rows"], len(months))
    return {"run_dir": str(run_dir), "profile_path": str(profile_path), "collected_at": profile["collected_at"]}
