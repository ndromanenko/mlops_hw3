import json
import os

from kafka import KafkaConsumer

from db import get_connection, init_table, insert_score
from logger_config import get_logger

BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
SCORING_TOPIC = os.getenv("KAFKA_RESULT_TOPIC", "scoring")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "db-writer")
LOG_EVERY = int(os.getenv("LOG_EVERY", "1000"))

log = get_logger("db_writer")


def main():
    conn = get_connection()
    init_table(conn)
    log.info("Подключился к таблице")

    consumer = KafkaConsumer(
        SCORING_TOPIC,
        bootstrap_servers=BROKERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    log.info(f"Слушаю топик '{SCORING_TOPIC}'")

    written = 0
    for message in consumer:
        record = message.value
        try:
            insert_score(
                conn,
                {
                    "transaction_id": record["transaction_id"],
                    "score": record["score"],
                    "fraud_flag": record["fraud_flag"],
                    "model_version": record["model_version"],
                },
            )
        except Exception:
            log.exception(f"Не удалось записать результат {record['transaction_id']}")
            continue

        written += 1
        if written % LOG_EVERY == 0:
            log.info(f"Записано строк: {written}")
