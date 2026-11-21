import json
import logging

import psycopg
from confluent_kafka import Consumer

from app.core.settings import DECISIONS_TOPIC, KAFKA_BOOTSTRAP, SESSION_TOPIC, database_dsn
from app.infra.repositories import save_decision, save_session_event

log = logging.getLogger("persister")
BATCH_SIZE = 200


def main() -> None:
  logging.basicConfig(level=logging.INFO)
  consumer = Consumer(
    {
      "bootstrap.servers": KAFKA_BOOTSTRAP,
      "group.id": "persister",
      "auto.offset.reset": "earliest",
      "enable.auto.commit": False,
    }
  )
  consumer.subscribe([SESSION_TOPIC, DECISIONS_TOPIC])
  log.info("persister started")

  with psycopg.connect(database_dsn()) as conn:
    while True:
      messages = consumer.consume(num_messages=BATCH_SIZE, timeout=0.5)
      if not messages:
        continue
      with conn.transaction(), conn.cursor() as cur:
        for msg in messages:
          if msg.error():
            log.error("kafka error: %s", msg.error())
            continue
          try:
            payload = json.loads(msg.value())
            with conn.transaction():
              if msg.topic() == SESSION_TOPIC:
                save_session_event(cur, payload)
              else:
                save_decision(cur, payload)
          except Exception:
            log.exception("failed to persist message from %s", msg.topic())
      consumer.commit(asynchronous=False)


if __name__ == "__main__":
  main()
