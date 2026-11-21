import math

SQL_FEATURES = [
  "amount",
  "amount_ratio",
  "src_tx_10m",
  "src_amount_10m",
  "src_age_hours",
  "src_inflow_24h",
  "src_inflow_senders_60m",
  "device_age_minutes",
  "mins_since_password_change",
  "mins_since_phone_change",
  "mins_since_device_change",
  "otp_15m",
  "hour_of_day",
  "tgt_age_hours",
  "tgt_is_merchant",
  "tgt_senders_60m",
  "tgt_tx_60m",
  "tgt_avg_amount_60m",
  "tgt_inflow_24h",
  "tgt_outflow_24h",
  "pair_first_time",
]

CHANNELS = ["transfer", "qr", "bill_payment", "topup", "withdrawal"]
MODEL_COLUMNS = SQL_FEATURES + [f"channel_{c}" for c in CHANNELS]

FEATURES_QUERY = (
  "SELECT * FROM compute_features("
  "%s::text, %s::text, %s::numeric, %s::text, %s::text, %s::timestamptz)"
)


def to_vector(row: dict, channel: str) -> list[float]:
  values = [math.nan if row[name] is None else float(row[name]) for name in SQL_FEATURES]
  values += [1.0 if channel == c else 0.0 for c in CHANNELS]
  return values
