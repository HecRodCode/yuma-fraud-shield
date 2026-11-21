import json

from confluent_kafka import Producer


class Publisher:
  def __init__(self, bootstrap: str) -> None:
    self._producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 5})

  def publish(self, topic: str, key: str, payload: dict) -> None:
    try:
      self._producer.produce(topic, key=key, value=json.dumps(payload, default=str))
      self._producer.poll(0)
    except BufferError:
      self._producer.poll(0.1)

  def flush(self) -> None:
    self._producer.flush(5)
