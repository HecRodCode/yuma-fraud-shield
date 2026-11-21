import argparse
import time
from datetime import timedelta

import numpy as np

from simulator.generators.fraud import SCENARIOS, Context
from simulator.settings import database_dsn
from simulator.sinks.api import create_client, score_payload
from simulator.sinks.kafka import EventPublisher
from simulator.sinks.postgres import departments, load_customers, virtual_now


def run_attack(args: argparse.Namespace) -> None:
  rng = np.random.default_rng(args.seed)
  dsn = database_dsn()
  ctx = Context(rng=rng, customers=list(load_customers(dsn).values()), departments=departments(dsn))
  start = virtual_now(dsn) + timedelta(minutes=1)
  batch = SCENARIOS[args.type](ctx, start)

  timeline = [(e.occurred_at, "event", e) for e in batch.events]
  timeline += [(t.occurred_at, "tx", t) for t in batch.transactions]
  timeline.sort(key=lambda item: item[0])

  publisher = EventPublisher()
  print(f"attack={args.type} events={len(batch.events)} transactions={len(batch.transactions)}", flush=True)
  started = time.monotonic()
  with create_client() as client:
    for at, kind, item in timeline:
      wait = (at - start).total_seconds() / args.speedup
      time.sleep(max(0.0, started + wait - time.monotonic()))
      if kind == "event":
        publisher.publish(item)
        publisher.flush()
        continue
      body = client.post("/score", json=score_payload(item)).json()
      reason = body["reasons"][0]["text"] if body.get("reasons") else ""
      print(
        f"{item.operation_type:<26} COP {item.amount:>12,.0f}  "
        f"{body['action']:<9} score={body['score']:.3f}  {reason}",
        flush=True,
      )
  publisher.flush()
