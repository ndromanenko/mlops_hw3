import logging
from pathlib import Path

import pandas as pd

from pipeline.registry import load_model, model_path, read_latest_version, write_json
from pipeline.retrain.fit_catboost import split_xy
from pipeline.settings import FRAUD_THRESHOLD, INITIAL_VERSION, METRIC_TOLERANCE

logger = logging.getLogger(__name__)


def score_model(model, x: pd.DataFrame, y: pd.Series) -> dict:
    from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

    proba = model.predict_proba(x[model.feature_names_])[:, 1]
    return {
        "pr_auc": float(average_precision_score(y, proba)),
        "roc_auc": float(roc_auc_score(y, proba)),
        "f1": float(f1_score(y, proba >= FRAUD_THRESHOLD, zero_division=0)),
    }


def format_comparison(evaluation: dict, rows: int, frauds: int) -> str:
    candidate, champion = evaluation["candidate_metrics"], evaluation["champion_metrics"]
    lines = [
        f"Сравнение на test-месяце {evaluation['test_month']} ({rows:,} строк, {frauds} фрод):",
        f"  {'метрика':<9}{'кандидат ' + evaluation['version']:<28}{'прод ' + str(evaluation['champion_version'])}",
    ]
    for metric in ("pr_auc", "roc_auc", "f1"):
        prod = f"{champion[metric]:.4f}" if champion else "-"
        lines.append(f"  {metric:<9}{candidate[metric]:<28.4f}{prod}")
    lines.append(f"  решение: {evaluation['decision']} ({evaluation['reason']})")
    return "\n".join(lines)


def evaluate_candidate(fit_info: dict) -> dict:
    """Считает метрики кандидата и текущей prod-модели на test-месяце и решает, публиковать ли."""
    run_dir = Path(fit_info["run_dir"])
    x_test, y_test = split_xy(pd.read_parquet(run_dir / "test_proc.parquet"))
    candidate = score_model(load_model(Path(fit_info["candidate_path"])), x_test, y_test)

    champion_version = read_latest_version()
    if champion_version in (None, INITIAL_VERSION):
        champion = None
        decision = "published"
        reason = f"в проде {champion_version}: первую модель DAG публикуем без сравнения"
    else:
        champion = score_model(load_model(model_path(champion_version)), x_test, y_test)
        threshold = champion["pr_auc"] - METRIC_TOLERANCE
        decision = "published" if candidate["pr_auc"] >= threshold else "rejected"
        reason = f"PR-AUC кандидата {candidate['pr_auc']:.4f} vs порог {threshold:.4f} (прод {champion['pr_auc']:.4f} - {METRIC_TOLERANCE})"

    evaluation = {
        **fit_info,
        "candidate_metrics": candidate,
        "champion_version": champion_version,
        "champion_metrics": champion,
        "decision": decision,
        "reason": reason,
    }
    write_json(run_dir / "evaluation.json", evaluation)
    logger.info(format_comparison(evaluation, len(y_test), int(y_test.sum())))
    return evaluation


def choose_deployment(evaluation: dict) -> str:
    return "publish_model" if evaluation["decision"] == "published" else "reject_model"
