import json

from confluent_kafka import Producer

from simulator.domain.models import SessionEvent
from simulator.settings import KAFKA_BOOTSTRAP, SESSION_TOPIC


class EventPublisher:
  def __init__(self) -> None:
    self._producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

  def publish(self, event: SessionEvent) -> None:
    self._producer.produce(
      SESSION_TOPIC,
      key=event.customer_id,
      value=json.dumps(
        {
          "id": event.id,
          "customer_id": event.customer_id,
          "type": event.type,
          "device_id": event.device_id,
          "os": event.os,
          "ip_department": event.ip_department,
          "result": event.result,
          "occurred_at": event.occurred_at.isoformat(),
        }
      ),
    )
    self._producer.poll(0)

  def flush(self) -> None:
    self._producer.flush()
