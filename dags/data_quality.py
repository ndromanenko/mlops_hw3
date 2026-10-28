from datetime import datetime, timedelta

from airflow.decorators import dag, task

from pipeline.dq.collect_dataset_profile import collect_dataset_profile
from pipeline.dq.evaluate_dq_rules import evaluate_dq_rules
from pipeline.dq.publish_dq_report import publish_dq_report
from pipeline.dq.render_dq_report import render_dq_report


@dag(
    dag_id="data_quality",
    description="Раз в 10 минут проверяет витрину по 5 правилам DQ и публикует HTML-отчёт",
    schedule="*/10 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=10),
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["mlops", "dq"],
)
def data_quality():
    profile = task(collect_dataset_profile, task_id="collect_dataset_profile")(run_id="{{ run_id }}")
    results = task(evaluate_dq_rules, task_id="evaluate_dq_rules")(profile)
    report = task(render_dq_report, task_id="render_dq_report")(results)
    task(publish_dq_report, task_id="publish_dq_report")(report)


data_quality()
