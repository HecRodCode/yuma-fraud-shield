#!/bin/bash
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
KAFKA_TOPICS=/opt/kafka/bin/kafka-topics.sh

for topic in session-events decisions; do
  $KAFKA_TOPICS --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$topic" --partitions 3 --replication-factor 1
done

$KAFKA_TOPICS --bootstrap-server "$BOOTSTRAP" --list
