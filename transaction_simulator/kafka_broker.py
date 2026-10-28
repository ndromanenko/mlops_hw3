import json
import os
import random
import time
import uuid

import pandas as pd
from kafka import KafkaProducer

from logger_config import get_logger

BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TRANSACTIONS_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
CSV_PATH = os.getenv("TRANSACTIONS_CSV_PATH", "/data/test.csv")
SEND_INTERVAL_SECONDS = float(os.getenv("SEND_INTERVAL_SECONDS", "0.2"))
LOG_EVERY = int(os.getenv("LOG_EVERY", "1000"))

log = get_logger("transaction_simulator")


def build_message(row):
    return {"transaction_id": str(uuid.uuid4()), "data": json.loads(row.to_json())}


def main():
    df = pd.read_csv(CSV_PATH)
    log.info(f"Прочитано {len(df)} транзакций из {CSV_PATH}")

    producer = KafkaProducer(
        bootstrap_servers=BROKERS,
        value_serializer=lambda x: json.dumps(x).encode("utf-8"),
    )
    log.info(f"Отправляю в '{TRANSACTIONS_TOPIC}' раз в {SEND_INTERVAL_SECONDS} с")

    sent = 0
    while True:
        row = df.iloc[random.randrange(len(df))]
        producer.send(TRANSACTIONS_TOPIC, value=build_message(row))
        sent += 1
        if sent % LOG_EVERY == 0:
            log.info(f"Отправлено транзакций: {sent}")
        time.sleep(SEND_INTERVAL_SECONDS)
