from dataclasses import dataclass, field

import yaml

from app.core.settings import CONFIG_DIR

RULE_ACTIONS = {"restricted_destination": "reject", "amount_cap": "hold"}


@dataclass
class Rules:
  restricted_destinations: set[str] = field(default_factory=set)
  amount_caps: dict[str, float] = field(default_factory=dict)

  def evaluate(self, destination_id: str, operation_type: str, amount: float) -> list[dict]:
    cap = self.amount_caps.get(operation_type, 0)
    return [
      {
        "rule": "restricted_destination",
        "fired": destination_id in self.restricted_destinations,
        "limit": None,
        "value": None,
      },
      {"rule": "amount_cap", "fired": bool(cap and amount > cap), "limit": cap, "value": amount},
    ]


def load_rules() -> Rules:
  data = yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text()) or {}
  return Rules(
    restricted_destinations=set(data.get("restricted_destinations") or []),
    amount_caps=data.get("amount_caps") or {},
  )
