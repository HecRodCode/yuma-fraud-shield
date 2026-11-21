import argparse
import time

import httpx
import psycopg

from simulator.settings import API_URL, database_dsn

PENDING_BASELINE = (
  "SELECT count(*) FROM transactions t "
  "WHERE NOT EXISTS (SELECT 1 FROM baseline_decisions b WHERE b.transaction_id = t.id)"
)


def wait_for_baseline(timeout: float) -> None:
  deadline = time.monotonic() + timeout
  with psycopg.connect(database_dsn(), autocommit=True) as conn:
    while time.monotonic() < deadline:
      pending = conn.execute(PENDING_BASELINE).fetchone()[0]
      print(f"baseline pending={pending}", flush=True)
      if pending == 0:
        return
      time.sleep(5)
  raise SystemExit("baseline did not finish in time")


def run_evaluate(args: argparse.Namespace) -> None:
  wait_for_baseline(args.timeout)
  print("scoring with Yuma Shield...", flush=True)
  response = httpx.post(
    f"{API_URL}/admin/replay", params={"all": str(args.all).lower()}, timeout=args.timeout
  )
  response.raise_for_status()
  print(response.json(), flush=True)
