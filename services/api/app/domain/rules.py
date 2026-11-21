from dataclasses import dataclass, field

import yaml

from app.core.settings import CONFIG_DIR


@dataclass
class Rules:
  restricted_accounts: set[str] = field(default_factory=set)
  amount_caps: dict[str, float] = field(default_factory=dict)

  def evaluate(self, target_account: str, channel: str, amount: float) -> list[dict]:
    cap = self.amount_caps.get(channel, 0)
    return [
      {
        "rule": "restricted_account",
        "fired": target_account in self.restricted_accounts,
        "limit": None,
        "value": None,
      },
      {"rule": "amount_cap", "fired": bool(cap and amount > cap), "limit": cap, "value": amount},
    ]


def load_rules() -> Rules:
  data = yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text()) or {}
  return Rules(
    restricted_accounts=set(data.get("restricted_accounts") or []),
    amount_caps=data.get("amount_caps") or {},
  )
