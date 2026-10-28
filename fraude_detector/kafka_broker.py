import json
import os

from kafka import KafkaConsumer, KafkaProducer

from inference import ensure_bootstrap, predict
from logger_config import get_logger

BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
INPUT_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
OUTPUT_TOPIC = os.getenv("KAFKA_RESULT_TOPIC", "scoring")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "ml-scorer")
LOG_EVERY = int(os.getenv("LOG_EVERY", "1000"))

log = get_logger("fraud_detector")


def score_transaction(data):
    result = predict([data]).iloc[0]
    return {
        "score": float(result["score"]),
        "fraud_flag": int(result["fraud_flag"]),
        "model_version": result["model_version"],
    }


def main():
    ensure_bootstrap()
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=BROKERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    producer = KafkaProducer(
        bootstrap_servers=BROKERS,
        value_serializer=lambda x: json.dumps(x).encode("utf-8"),
    )

    log.info(f"Слушаю топик '{INPUT_TOPIC}', публикую в '{OUTPUT_TOPIC}'")
    processed = 0
    for message in consumer:
        payload = message.value
        transaction_id = payload["transaction_id"]
        try:
            prediction = score_transaction(payload["data"])
        except Exception:
            log.exception("Не удалось обработать транзакцию {}", transaction_id)
            continue

        producer.send(OUTPUT_TOPIC, value={"transaction_id": transaction_id, **prediction})

        processed += 1
        if prediction["fraud_flag"]:
            log.warning(f"id={transaction_id} score={prediction["score"]} model={prediction["model_version"]}")
        if processed % LOG_EVERY == 0:
            log.info(f"Обработано транзакций: {processed}")
