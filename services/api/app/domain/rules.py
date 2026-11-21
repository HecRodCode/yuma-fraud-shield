from dataclasses import dataclass, field

import yaml

from app.core.settings import CONFIG_DIR


@dataclass
class Rules:
  restricted_accounts: set[str] = field(default_factory=set)
  amount_caps: dict[str, float] = field(default_factory=dict)

  def check(self, target_account: str, channel: str, amount: float) -> str | None:
    if target_account in self.restricted_accounts:
      return "restricted_account"
    cap = self.amount_caps.get(channel)
    if cap and amount > cap:
      return "amount_cap"
    return None


def load_rules() -> Rules:
  data = yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text()) or {}
  return Rules(
    restricted_accounts=set(data.get("restricted_accounts") or []),
    amount_caps=data.get("amount_caps") or {},
  )
