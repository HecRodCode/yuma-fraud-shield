import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np

from simulator.domain.models import Transaction
from simulator.generators.legit import build_legit_transaction
from simulator.settings import database_dsn
from simulator.sinks.api import create_client, score_payload
from simulator.sinks.postgres import load_population


def run_live(args: argparse.Namespace) -> None:
  rng = np.random.default_rng(args.seed)
  accounts = load_population(database_dsn())
  by_id = {a.id: a for a in accounts}
  regular = [a for a in accounts if a.devices and not a.is_merchant]
  weights = np.array([a.daily_rate for a in regular])
  weights = weights / weights.sum()
  counts = {"approve": 0, "challenge": 0, "hold": 0}
  latencies: list[float] = []

  def send(tx: Transaction) -> None:
    response = client.post("/score", json=score_payload(tx))
    if response.status_code == 200:
      body = response.json()
      counts[body["action"]] += 1
      latencies.append(body["latency_ms"])

  with create_client() as client, ThreadPoolExecutor(32) as pool:
    started = time.monotonic()
    sent = 0
    while time.monotonic() - started < args.duration:
      acc = regular[int(rng.choice(len(regular), p=weights))]
      now = datetime.now(timezone.utc)
      tx = build_legit_transaction(rng, acc, by_id, regular, acc.devices[-1], now)
      if tx is not None:
        pool.submit(send, tx)
        sent += 1
      time.sleep(max(0.0, started + sent / args.tps - time.monotonic()))

  print(f"sent={sent} decisions={counts}")
  if latencies:
    print(f"latency_ms p50={np.percentile(latencies, 50):.1f} p95={np.percentile(latencies, 95):.1f}")
