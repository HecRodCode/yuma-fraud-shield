from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class StaticRules:
  batch_minutes: int
  amount_caps: dict[str, float]
  night: dict
  daily_cap: float
  restricted_enabled: bool
  restricted_delay_hours: int

  def evaluate(self, row: dict) -> tuple[str | None, list[dict]]:
    amount = row["amount"]
    cap = self.amount_caps.get(row["channel"], 0)
    in_night = self.night["start_hour"] <= row["hour_of_day"] <= self.night["end_hour"]

    checks = [
      {"rule": "amount_cap", "limit": cap, "value": amount,
       "fired": bool(cap and amount > cap)},
      {"rule": "night_cap", "limit": self.night["cap"], "value": amount,
       "fired": bool(self.night["cap"] and in_night and amount > self.night["cap"])},
      {"rule": "daily_cap", "limit": self.daily_cap, "value": row["day_total"],
       "fired": bool(self.daily_cap and row["day_total"] > self.daily_cap)},
      {"rule": "restricted_account", "limit": None, "value": None,
       "fired": bool(self.restricted_enabled and row["restricted_target"])},
    ]
    fired = next((c["rule"] for c in checks if c["fired"]), None)
    return fired, checks


def load_rules(path: Path) -> StaticRules:
  data = yaml.safe_load(path.read_text())
  return StaticRules(
    batch_minutes=int(data["batch_minutes"]),
    amount_caps=data["amount_caps"],
    night=data["night"],
    daily_cap=float(data["daily_cap"]),
    restricted_enabled=bool(data["restricted_list"]["enabled"]),
    restricted_delay_hours=int(data["restricted_list"]["delay_hours"]),
  )
