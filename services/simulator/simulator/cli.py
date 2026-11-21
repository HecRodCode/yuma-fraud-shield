import argparse

from simulator.commands.attack import run_attack
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

  return parser


def main() -> None:
  args = build_parser().parse_args()
  args.handler(args)
