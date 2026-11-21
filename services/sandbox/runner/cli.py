import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from runner.mapping import to_sandbox_decision, to_score_request

API_URL = os.environ.get("API_URL", "http://localhost:8000")
SANDBOX_URL = os.environ.get("SANDBOX_URL", "http://localhost:8090")
OUT_DIR = Path(os.environ.get("OUT_DIR", "/out"))


def decide(api: httpx.Client, sandbox: httpx.Client, tx: dict) -> str:
  response = api.post("/score", json=to_score_request(tx))
  response.raise_for_status()
  body = response.json()
  sandbox.post("/v1/decisiones", json=to_sandbox_decision(body)).raise_for_status()
  return body["action"]


def run(args: argparse.Namespace) -> None:
  with httpx.Client(base_url=API_URL, timeout=10) as api, \
       httpx.Client(base_url=SANDBOX_URL, timeout=10) as sandbox, \
       ThreadPoolExecutor(args.workers) as pool:
    if args.reset:
      sandbox.post("/v1/reiniciar").raise_for_status()

    skipped = decided = 0
    actions: dict[str, int] = {}
    started = time.monotonic()
    while args.limit is None or decided < args.limit:
      batch = sandbox.get("/v1/transacciones/siguiente", params={"cantidad": args.workers}).json()
      transactions = batch["transacciones"]
      if not transactions:
        break
      pending = [t for t in transactions if t["fecha_hora"] >= args.start]
      skipped += len(transactions) - len(pending)
      for action in pool.map(lambda t: decide(api, sandbox, t), pending):
        actions[action] = actions.get(action, 0) + 1
      decided += len(pending)
      if decided and decided % 1000 < len(pending):
        print(f"decided={decided} skipped={skipped} remaining={batch['restantes']}", flush=True)

    elapsed = time.monotonic() - started
    metrics = sandbox.get("/v1/metricas").json()

  report = {"start": args.start, "decided": decided, "skipped": skipped,
            "actions": actions, "elapsed_s": round(elapsed, 1), "sandbox_metrics": metrics}
  OUT_DIR.mkdir(parents=True, exist_ok=True)
  (OUT_DIR / "sandbox_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
  print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> None:
  parser = argparse.ArgumentParser(prog="runner")
  parser.add_argument("--start", default="2026-10-01 00:00:00",
                      help="decide only transactions from this local time on")
  parser.add_argument("--workers", type=int, default=32)
  parser.add_argument("--limit", type=int, default=None)
  parser.add_argument("--reset", action="store_true")
  run(parser.parse_args())
