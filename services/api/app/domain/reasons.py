import math

RULE_REASONS = {
  "restricted_account": "Target account is on a restricted list",
  "amount_cap": "Amount exceeds the cap allowed for this channel",
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


TEMPLATES = {
  "amount": lambda v: f"Amount is {_cop(v)}",
  "amount_ratio": lambda v: (
    "No spending history to compare with"
    if math.isnan(v)
    else f"Amount is {v:.1f}x the sender's 30-day average"
  ),
  "src_tx_10m": _count("{n} outgoing transactions in the last 10 minutes"),
  "src_amount_10m": lambda v: f"{_cop(v)} sent in the last 10 minutes",
  "src_age_hours": lambda v: f"Sender account is {_duration(v * 60)} old",
  "src_inflow_24h": lambda v: f"Sender received {_cop(v)} in the last 24 hours",
  "src_inflow_senders_60m": _count("Sender received money from {n} different accounts in the last hour"),
  "device_age_minutes": lambda v: (
    "Device never seen on this account"
    if v == 0
    else f"Device first seen {_duration(v)} ago"
  ),
  "mins_since_password_change": _since("password change"),
  "mins_since_phone_change": _since("phone number change"),
  "mins_since_device_change": _since("device change"),
  "otp_15m": _count("{n} OTP requests in the last 15 minutes"),
  "hour_of_day": lambda v: f"Transaction made at {int(v):02d}:00",
  "tgt_age_hours": lambda v: (
    "Target account is unknown"
    if math.isnan(v)
    else f"Target account is {_duration(v * 60)} old"
  ),
  "tgt_is_merchant": lambda v: "Target is a merchant" if v else "Target is a personal account",
  "tgt_senders_60m": _count("Target received money from {n} different accounts in the last hour"),
  "tgt_tx_60m": _count("Target received {n} payments in the last hour"),
  "tgt_avg_amount_60m": lambda v: (
    "No recent payments to the target"
    if math.isnan(v)
    else f"Average payment to the target in the last hour is {_cop(v)}"
  ),
  "tgt_inflow_24h": lambda v: f"Target received {_cop(v)} in the last 24 hours",
  "tgt_outflow_24h": lambda v: f"Target sent out {_cop(v)} in the last 24 hours",
  "pair_first_time": lambda v: (
    "First transaction between these accounts" if v else "Sender has paid this target before"
  ),
}


def describe(feature: str, value: float) -> str:
  if feature.startswith("channel_"):
    return f"Channel is {feature.removeprefix('channel_').replace('_', ' ')}"
  return TEMPLATES[feature](value)


def build_reasons(
  features: list[str], values: list[float], contributions: list[float], top: int = 3
) -> list[dict]:
  ranked = sorted(range(len(features)), key=lambda i: abs(contributions[i]), reverse=True)
  reasons = []
  for i in ranked:
    if len(reasons) == top:
      break
    if features[i].startswith("channel_") and values[i] == 0:
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
