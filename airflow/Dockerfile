FROM apache/airflow:2.10.5-python3.11

USER airflow
# numpy и pandas зафиксированы под constraints Airflow 2.10: более новые версии ломают сам Airflow.
RUN pip install --no-cache-dir \
    "numpy==1.26.4" \
    "pandas==2.1.4" \
    "scikit-learn==1.5.2" \
    "catboost==1.2.10" \
    "cloudpickle==2.2.1" \
    "loguru==0.7.3" \
    && python -c "import catboost, sklearn, pandas, pyarrow, psycopg2, jinja2, loguru; print(catboost.__version__, sklearn.__version__, pandas.__version__)"

USER root
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
