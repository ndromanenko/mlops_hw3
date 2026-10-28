import json
import os

from kafka import KafkaConsumer, KafkaProducer

from logger_config import get_logger

BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TRANSACTIONS_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
SCORING_TOPIC = os.getenv("KAFKA_RESULT_TOPIC", "scoring")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "interface")

log = get_logger("interface")


def send_transactions(df, progress_callback=None):
    producer = KafkaProducer(
        bootstrap_servers=BROKERS,
        value_serializer=lambda x: json.dumps(x).encode("utf-8"),
    )
    total = len(df)
    log.info(f"На отправку {total} транзакций в топик '{TRANSACTIONS_TOPIC}'")
    for i, (_, row) in enumerate(df.iterrows()):
        data = json.loads(row.to_json())
        transaction_id = data.get("transaction_id", i)
        producer.send(
            TRANSACTIONS_TOPIC,
            value={"transaction_id": str(transaction_id), "data": data},
        )
        if progress_callback:
            progress_callback((i + 1) / total)

    producer.flush()
    producer.close()
    log.info(f"Отправлено транзакций: {total}")
    return total


def consume_scores(limit=None, timeout_ms=5000):
    consumer = KafkaConsumer(
        SCORING_TOPIC,
        bootstrap_servers=BROKERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        consumer_timeout_ms=timeout_ms,
    )
    results = []
    for message in consumer:
        results.append(message.value)
        if limit and len(results) >= limit:
            break
    consumer.close()
    log.info(f"Прочитано результатов: {len(results)} из топика '{SCORING_TOPIC}'")
    return results
