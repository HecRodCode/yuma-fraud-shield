from dataclasses import dataclass
from pathlib import Path

import yaml

OUTFLOWS = ("instant_transfer", "correspondent_withdrawal", "atm_withdrawal")
WITHDRAWALS = ("correspondent_withdrawal", "atm_withdrawal")
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class StaticRules:
  batch_minutes: int
  params: dict[str, dict]

  def evaluate(self, row: dict) -> tuple[list[str], str | None]:
    p = self.params
    amount = row["amount"]
    kind = row["operation_type"]
    transfer = kind == "instant_transfer"
    withdrawal = kind in WITHDRAWALS
    outflow = kind in OUTFLOWS

    fired = {
      "R001": transfer and amount >= p["R001"]["min_amount"],
      "R002": outflow and row["new_device"] and amount >= p["R002"]["min_amount"],
      "R003": outflow and row["hour_of_day"] <= p["R003"]["max_hour"]
        and amount >= p["R003"]["min_amount"],
      "R004": outflow and row["outflows_60m"] >= p["R004"]["min_outflows_60m"],
      "R005": transfer and row["new_destination"]
        and amount >= p["R005"]["min_balance_ratio"] * row["balance_before"]
        and amount >= p["R005"]["min_amount"],
      "R006": transfer and row["password_change_24h"] and amount >= p["R006"]["min_amount"],
      "R007": outflow and row["sim_change_48h"] and amount >= p["R007"]["min_amount"],
      "R008": withdrawal and row["account_age_days"] < p["R008"]["max_account_age_days"]
        and amount >= p["R008"]["min_amount"],
      "R009": outflow and row["ip_department_mismatch"] and amount >= p["R009"]["min_amount"],
      "R010": outflow and row["daily_total"] >= p["R010"]["min_daily_total"],
      "R011": kind == "qr_payment" and amount >= p["R011"]["min_amount"],
      "R012": withdrawal and amount >= p["R012"]["min_amount"],
    }
    ids = [rule for rule, hit in fired.items() if hit]
    if not ids:
      return [], None
    top = max((p[r]["severity"] for r in ids), key=SEVERITY_ORDER.get)
    return ids, top


def load_rules(path: Path) -> StaticRules:
  data = yaml.safe_load(path.read_text())
  return StaticRules(batch_minutes=int(data["batch_minutes"]), params=data["rules"])
