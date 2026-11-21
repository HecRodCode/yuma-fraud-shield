import argparse
import time
from datetime import datetime, timezone

import numpy as np

from simulator.generators.fraud import SCENARIOS, Context
from simulator.settings import database_dsn
from simulator.sinks.api import create_client, score_payload
from simulator.sinks.kafka import EventPublisher
from simulator.sinks.postgres import insert_accounts, load_population


def run_attack(args: argparse.Namespace) -> None:
  rng = np.random.default_rng(args.seed)
  accounts = load_population(database_dsn())
  ctx = Context(
    rng=rng,
    victims=[a for a in accounts if a.devices and not a.is_merchant],
    merchants=[a for a in accounts if a.is_merchant and a.devices],
  )
  t0 = datetime.now(timezone.utc)
  batch = SCENARIOS[args.type](ctx, t0)
  insert_accounts(database_dsn(), batch.accounts)

  timeline = [(e.occurred_at, "event", e) for e in batch.events]
  timeline += [(t.created_at, "tx", t) for t in batch.transactions]
  timeline.sort(key=lambda item: item[0])

  publisher = EventPublisher()
  print(f"attack={args.type} events={len(batch.events)} transactions={len(batch.transactions)}")
  started = time.monotonic()
  with create_client() as client:
    for ts, kind, item in timeline:
      offset = max(0.0, (ts - t0).total_seconds()) / args.speedup
      time.sleep(max(0.0, started + offset - time.monotonic()))
      if kind == "event":
        publisher.publish(item, ts if ts < t0 else datetime.now(timezone.utc))
        publisher.flush()
        continue
      body = client.post("/score", json=score_payload(item)).json()
      reason = body["reasons"][0]["text"] if body.get("reasons") else ""
      print(
        f"{item.channel:<12} COP {item.amount:>12,.0f}  "
        f"{body['action']:<9} score={body['score']:.3f}  {reason}"
      )
  publisher.flush()
