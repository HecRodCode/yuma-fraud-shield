import math
from datetime import datetime
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

OPERATION_TYPES = [
  "instant_transfer", "qr_payment", "bill_payment", "correspondent_withdrawal",
  "atm_withdrawal", "mobile_topup", "virtual_card_purchase",
]
CHANNELS = ["app", "correspondent", "atm"]
DESTINATION_TYPES = [
  "yuma_account", "other_bank", "merchant", "correspondent", "atm", "utility", "carrier",
]

HISTORY_FEATURES = [
  "out_tx_10m",
  "out_tx_60m",
  "out_amount_24h",
  "avg_amount_30d",
  "tx_count_30d",
  "failed_logins_24h",
  "mins_since_password_change",
  "mins_since_sim_change",
  "mins_since_device_registration",
  "device_age_minutes",
  "in_senders_60m",
  "in_senders_24h",
  "in_amount_24h",
  "dest_senders_60m",
  "dest_tx_60m",
  "dest_senders_24h",
  "dest_first_seen_hours",
  "dest_age_days",
]

TRANSACTION_FEATURES = [
  "amount",
  "balance_ratio",
  "amount_vs_avg_30d",
  "new_destination",
  "new_device",
  "password_change_24h",
  "sim_change_48h",
  "ip_department_mismatch",
  "account_age_days",
  "hour_of_day",
  "day_of_week",
]

MODEL_COLUMNS = (
  TRANSACTION_FEATURES
  + HISTORY_FEATURES
  + [f"operation_{v}" for v in OPERATION_TYPES]
  + [f"channel_{v}" for v in CHANNELS]
  + [f"destination_{v}" for v in DESTINATION_TYPES]
)

FEATURES_QUERY = (
  "SELECT * FROM compute_features(%s::text, %s::text, %s::text, %s::timestamptz)"
)


def _num(value) -> float:
  return math.nan if value is None else float(value)


def build_row(tx: dict, history: dict) -> list[float]:
  amount = float(tx["amount"])
  balance = float(tx["balance_before"])
  avg_30d = history["avg_amount_30d"]
  local = tx["occurred_at"].astimezone(BOGOTA)

  values = {
    "amount": amount,
    "balance_ratio": amount / balance if balance > 0 else math.nan,
    "amount_vs_avg_30d": amount / avg_30d if avg_30d else math.nan,
    "new_destination": float(tx["new_destination"]),
    "new_device": float(tx["new_device"]),
    "password_change_24h": float(tx["password_change_24h"]),
    "sim_change_48h": float(tx["sim_change_48h"]),
    "ip_department_mismatch": float(tx["ip_department_mismatch"]),
    "account_age_days": float(tx["account_age_days"]),
    "hour_of_day": float(local.hour),
    "day_of_week": float(local.weekday()),
  }
  for name in HISTORY_FEATURES:
    values[name] = _num(history[name])
  for v in OPERATION_TYPES:
    values[f"operation_{v}"] = float(tx["operation_type"] == v)
  for v in CHANNELS:
    values[f"channel_{v}"] = float(tx["channel"] == v)
  for v in DESTINATION_TYPES:
    values[f"destination_{v}"] = float(tx["destination_type"] == v)
  return [values[c] for c in MODEL_COLUMNS]
