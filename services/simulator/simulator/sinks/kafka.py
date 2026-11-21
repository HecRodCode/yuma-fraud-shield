import json
from datetime import datetime

from confluent_kafka import Producer

from simulator.domain.models import SessionEvent
from simulator.settings import KAFKA_BOOTSTRAP, SESSION_TOPIC


class EventPublisher:
  def __init__(self) -> None:
    self._producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

  def publish(self, event: SessionEvent, occurred_at: datetime) -> None:
    self._producer.produce(
      SESSION_TOPIC,
      key=event.account_id,
      value=json.dumps(
        {
          "id": str(event.id),
          "account_id": event.account_id,
          "type": event.type,
          "device": event.device,
          "occurred_at": occurred_at.isoformat(),
        }
      ),
    )
    self._producer.poll(0)

  def flush(self) -> None:
    self._producer.flush()
