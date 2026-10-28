#!/usr/bin/env bash
set -euo pipefail

# artifacts смонтирован с хоста и общий с fraud_detector, который пишет туда от root.
mkdir -p /opt/airflow/artifacts/models /opt/airflow/artifacts/dq_reports /opt/airflow/airflow_state /opt/airflow/logs
chmod 777 /opt/airflow/artifacts /opt/airflow/artifacts/models /opt/airflow/artifacts/dq_reports \
  /opt/airflow/airflow_state /opt/airflow/logs

run_as_airflow() {
  /usr/sbin/runuser --preserve-environment --user airflow -- "$@"
}

run_as_airflow airflow db migrate
run_as_airflow airflow users create \
  --username "${_AIRFLOW_WWW_USER_USERNAME:-admin}" \
  --password "${_AIRFLOW_WWW_USER_PASSWORD:-admin}" \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  || true

exec /usr/sbin/runuser --preserve-environment --user airflow -- /entrypoint standalone
