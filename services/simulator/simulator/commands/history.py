import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np

from simulator.generators.history import build_history
from simulator.settings import database_dsn
from simulator.sinks.postgres import write_batch

BOGOTA = timezone(timedelta(hours=-5))


def run_history(args: argparse.Namespace) -> None:
  rng = np.random.default_rng(args.seed)
  end = datetime.now(BOGOTA).replace(hour=0, minute=0, second=0, microsecond=0)

  batch = build_history(rng, args.accounts, args.days, args.fraud_rate, end)
  write_batch(database_dsn(), batch, args.reset)

  frauds = Counter(t.fraud_type for t in batch.transactions if t.is_fraud)
  total = len(batch.transactions)
  print(f"accounts={len(batch.accounts)} events={len(batch.events)} transactions={total}")
  print(f"fraud={sum(frauds.values())} ({sum(frauds.values()) / total:.2%}) {dict(frauds)}")
