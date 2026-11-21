import math

RULE_REASONS = {
  "restricted_destination": "Destination is on the restricted list",
  "amount_cap": "Amount exceeds the cap allowed for this operation",
}

OPERATION_NAMES = {
  "instant_transfer": "instant transfer",
  "qr_payment": "QR payment",
  "bill_payment": "bill payment",
  "correspondent_withdrawal": "correspondent withdrawal",
  "atm_withdrawal": "ATM withdrawal",
  "mobile_topup": "mobile top-up",
  "virtual_card_purchase": "virtual card purchase",
}


def _cop(value: float) -> str:
  return f"COP {value:,.0f}"


def _duration(minutes: float) -> str:
  if minutes < 1:
    return "less than a minute"
  if minutes < 120:
    return f"{minutes:.0f} minutes"
  if minutes < 48 * 60:
    return f"{minutes / 60:.0f} hours"
  return f"{minutes / 1440:.0f} days"


def _since(label: str):
  def render(v: float) -> str:
    if math.isnan(v):
      return f"No {label} in the last 30 days"
    return f"{label.capitalize()} {_duration(v)} ago"
  return render


def _count(template: str):
  return lambda v: template.format(n=int(v))


def _flag(yes: str, no: str):
  return lambda v: yes if v else no


TEMPLATES = {
  "amount": lambda v: f"Amount is {_cop(v)}",
  "balance_ratio": lambda v: (
    "Balance is unknown" if math.isnan(v) else f"Amount is {v:.0%} of the available balance"
  ),
  "amount_vs_avg_30d": lambda v: (
    "No spending history to compare with"
    if math.isnan(v)
    else f"Amount is {v:.1f}x the customer's 30-day average"
  ),
  "new_destination": _flag(
    "First operation to this destination in 180 days", "Customer has paid this destination before"
  ),
  "new_device": _flag("Device registered in the last 24 hours", "Device is a familiar one"),
  "password_change_24h": _flag("Password changed in the last 24 hours", "No recent password change"),
  "sim_change_48h": _flag("SIM change reported in the last 48 hours", "No recent SIM change"),
  "ip_department_mismatch": _flag(
    "Connection comes from outside the customer's usual area", "Connection is from the usual area"
  ),
  "account_age_days": lambda v: f"Account is {_duration(v * 1440)} old",
  "hour_of_day": lambda v: f"Operation made at {int(v):02d}:00",
  "day_of_week": lambda v: "Operation made on a weekend" if v >= 5 else "Operation made on a weekday",
  "out_tx_10m": _count("{n} operations by the customer in the last 10 minutes"),
  "out_tx_60m": _count("{n} operations by the customer in the last hour"),
  "out_amount_24h": lambda v: f"{_cop(v)} moved by the customer in the last 24 hours",
  "avg_amount_30d": lambda v: (
    "No spending history" if math.isnan(v) else f"Customer's 30-day average is {_cop(v)}"
  ),
  "tx_count_30d": _count("{n} operations by the customer in the last 30 days"),
  "failed_logins_24h": _count("{n} failed logins in the last 24 hours"),
  "mins_since_password_change": _since("password change"),
  "mins_since_sim_change": _since("SIM change"),
  "mins_since_device_registration": _since("device registration"),
  "device_age_minutes": lambda v: (
    "Device never seen on this account" if v == 0 else f"Device first seen {_duration(v)} ago"
  ),
  "in_senders_60m": _count("Customer received money from {n} different people in the last hour"),
  "in_senders_24h": _count("Customer received money from {n} different people in the last 24 hours"),
  "in_amount_24h": lambda v: f"Customer received {_cop(v)} in the last 24 hours",
  "dest_senders_60m": _count("Destination received money from {n} different customers in the last hour"),
  "dest_tx_60m": _count("Destination received {n} payments in the last hour"),
  "dest_senders_24h": _count("Destination received money from {n} different customers in the last 24 hours"),
  "dest_first_seen_hours": lambda v: (
    "Destination never seen before" if math.isnan(v) else f"Destination first seen {_duration(v * 60)} ago"
  ),
  "dest_age_days": lambda v: (
    "Destination is not a Yuma account"
    if math.isnan(v)
    else f"Destination account is {_duration(v * 1440)} old"
  ),
}


def describe(feature: str, value: float) -> str:
  for prefix, label in (("operation_", "Operation"), ("channel_", "Channel"), ("destination_", "Destination")):
    if feature.startswith(prefix):
      name = feature.removeprefix(prefix)
      return f"{label} is {OPERATION_NAMES.get(name, name.replace('_', ' '))}"
  return TEMPLATES[feature](value)


def build_reasons(
  features: list[str], values: list[float], contributions: list[float], top: int = 3
) -> list[dict]:
  ranked = sorted(range(len(features)), key=lambda i: abs(contributions[i]), reverse=True)
  reasons = []
  for i in ranked:
    if len(reasons) == top:
      break
    if features[i].startswith(("operation_", "channel_", "destination_")) and values[i] == 0:
      continue
    reasons.append(
      {
        "feature": features[i],
        "text": describe(features[i], values[i]),
        "effect": "raises_risk" if contributions[i] > 0 else "lowers_risk",
        "impact": round(contributions[i], 3),
      }
    )
  return reasons
