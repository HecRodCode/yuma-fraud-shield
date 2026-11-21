import argparse

from simulator.commands.attack import run_attack
from simulator.commands.evaluate import run_evaluate
from simulator.commands.history import run_history
from simulator.commands.live import run_live
from simulator.generators.fraud import FRAUD_TYPES


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="simulator")
  sub = parser.add_subparsers(dest="command", required=True)

  history = sub.add_parser("history", help="generate a labeled history into PostgreSQL")
  history.add_argument("--accounts", type=int, default=5000)
  history.add_argument("--days", type=int, default=60)
  history.add_argument("--fraud-rate", type=float, default=0.01)
  history.add_argument("--seed", type=int, default=42)
  history.add_argument("--reset", action="store_true")
  history.set_defaults(handler=run_history)

  live = sub.add_parser("live", help="send legitimate traffic to the scoring API")
  live.add_argument("--tps", type=float, default=5)
  live.add_argument("--duration", type=float, default=30)
  live.add_argument("--seed", type=int, default=1)
  live.set_defaults(handler=run_live)

  attack = sub.add_parser("attack", help="launch one fraud scenario against the scoring API")
  attack.add_argument("type", choices=FRAUD_TYPES)
  attack.add_argument("--speedup", type=float, default=20)
  attack.add_argument("--seed", type=int, default=None)
  attack.set_defaults(handler=run_attack)

  evaluate = sub.add_parser("evaluate", help="wait for the baseline and score the stored transactions")
  evaluate.add_argument("--all", action="store_true")
  evaluate.add_argument("--timeout", type=float, default=900)
  evaluate.set_defaults(handler=run_evaluate)

  serve = sub.add_parser("serve", help="run the control service")
  serve.add_argument("--port", type=int, default=8001)
  serve.set_defaults(handler=run_serve)

  return parser


def run_serve(args: argparse.Namespace) -> None:
  import uvicorn

  uvicorn.run("simulator.control.app:app", host="0.0.0.0", port=args.port)


def main() -> None:
  args = build_parser().parse_args()
  args.handler(args)
