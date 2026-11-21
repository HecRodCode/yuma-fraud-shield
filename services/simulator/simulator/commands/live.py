import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import numpy as np

from simulator.domain.models import SimTransaction
from simulator.generators.legit import build_legit
from simulator.settings import database_dsn
from simulator.sinks.api import create_client, score_payload
from simulator.sinks.postgres import load_customers, virtual_now


def run_live(args: argparse.Namespace) -> None:
  rng = np.random.default_rng(args.seed)
  customers = list(load_customers(database_dsn()).values())
  weights = np.array([max(c.n_tx, 1) for c in customers], dtype=float)
  weights /= weights.sum()
  clock = virtual_now(database_dsn()) + timedelta(minutes=1)
  counts = {"approve": 0, "challenge": 0, "hold": 0, "reject": 0}
  latencies: list[float] = []

  def send(tx: SimTransaction) -> None:
    response = client.post("/score", json=score_payload(tx))
    if response.status_code == 200:
      body = response.json()
      counts[body["action"]] += 1
      latencies.append(body["latency_ms"])

  with create_client() as client, ThreadPoolExecutor(32) as pool:
    started = time.monotonic()
    sent = 0
    while time.monotonic() - started < args.duration:
      customer = customers[int(rng.choice(len(customers), p=weights))]
      at = clock + timedelta(seconds=(time.monotonic() - started) * args.clock_speed)
      pool.submit(send, build_legit(rng, customer, at))
      sent += 1
      time.sleep(max(0.0, started + sent / args.tps - time.monotonic()))

  print(f"sent={sent} decisions={counts}")
  if latencies:
    print(f"latency_ms p50={np.percentile(latencies, 50):.1f} p95={np.percentile(latencies, 95):.1f}")
