from datetime import datetime, timedelta

from airflow.decorators import dag, task

from pipeline.retrain.advance_training_pointer import advance_training_pointer
from pipeline.retrain.evaluate_candidate import choose_deployment, evaluate_candidate
from pipeline.retrain.extract_training_window import extract_training_window
from pipeline.retrain.fit_catboost import fit_catboost
from pipeline.retrain.preprocess_dataset import preprocess_dataset
from pipeline.retrain.publish_model import publish_model, reject_model
from pipeline.retrain.time_train_test_split import time_train_test_split


EVALUATION = "{{ ti.xcom_pull(task_ids='evaluate_candidate') }}"


@dag(
    dag_id="retrain_model",
    description="Раз в 5 минут сдвигает 3-месячное окно, обучает CatBoost и раскатывает его, если он не хуже прода",
    schedule="*/5 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=20),
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["mlops", "catboost"],
    render_template_as_native_obj=True,
)
def retrain_model():
    window = task(extract_training_window, task_id="extract_training_window")(run_id="{{ run_id }}")
    split = task(time_train_test_split, task_id="time_train_test_split")(window)
    processed = task(preprocess_dataset, task_id="preprocess_dataset")(split)
    fitted = task(fit_catboost, task_id="fit_catboost")(processed)
    evaluation = task(evaluate_candidate, task_id="evaluate_candidate")(fitted)
    branch = task.branch(choose_deployment, task_id="choose_deployment")(evaluation)
    published = task(publish_model, task_id="publish_model")(EVALUATION)
    rejected = task(reject_model, task_id="reject_model")(EVALUATION)
    advanced = task(
        advance_training_pointer,
        task_id="advance_training_pointer",
        trigger_rule="none_failed_min_one_success",
    )(EVALUATION)

    branch >> [published, rejected] >> advanced


retrain_model()
