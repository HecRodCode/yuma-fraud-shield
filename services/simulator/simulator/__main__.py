import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np

from .db import dsn_from_env, write_batch
from .history import build_history

BOGOTA = timezone(timedelta(hours=-5))


def main() -> None:
  parser = argparse.ArgumentParser(prog="simulator")
  sub = parser.add_subparsers(dest="command", required=True)

  history = sub.add_parser("history", help="generate a labeled history into PostgreSQL")
  history.add_argument("--accounts", type=int, default=5000)
  history.add_argument("--days", type=int, default=60)
  history.add_argument("--fraud-rate", type=float, default=0.01)
  history.add_argument("--seed", type=int, default=42)
  history.add_argument("--reset", action="store_true")

  args = parser.parse_args()
  rng = np.random.default_rng(args.seed)
  end = datetime.now(BOGOTA).replace(hour=0, minute=0, second=0, microsecond=0)

  batch = build_history(rng, args.accounts, args.days, args.fraud_rate, end)
  write_batch(dsn_from_env(), batch, args.reset)

  frauds = Counter(t.fraud_type for t in batch.transactions if t.is_fraud)
  total = len(batch.transactions)
  print(f"accounts={len(batch.accounts)} events={len(batch.events)} transactions={total}")
  print(f"fraud={sum(frauds.values())} ({sum(frauds.values()) / total:.2%}) {dict(frauds)}")


if __name__ == "__main__":
  main()
