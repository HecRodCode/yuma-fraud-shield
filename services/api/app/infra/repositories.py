import json
from datetime import datetime, timedelta, timezone


def ensure_customer(cur, customer_id: str, at: str, account_age_days: int = 0) -> None:
  joined = datetime.fromisoformat(at).date() - timedelta(days=account_age_days)
  cur.execute(
    "INSERT INTO customers (id, type, joined_on) VALUES (%s, 'person', %s) ON CONFLICT DO NOTHING",
    (customer_id, joined),
  )


def save_session_event(cur, event: dict) -> None:
  ensure_customer(cur, event["customer_id"], event["occurred_at"])
  cur.execute(
    "INSERT INTO session_events (id, customer_id, type, device_id, os, ip_department, result, "
    "occurred_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
    (
      event["id"], event["customer_id"], event["type"], event.get("device_id"), event.get("os"),
      event.get("ip_department"), event.get("result", "success"), event["occurred_at"],
    ),
  )


def save_decision(cur, message: dict, kafka: dict) -> None:
  tx = message["transaction"]
  decision = message["decision"]
  meta = message.get("meta") or {}

  ensure_customer(cur, tx["customer_id"], tx["occurred_at"], tx["account_age_days"])
  cur.execute(
    "INSERT INTO transactions (id, occurred_at, customer_id, operation_type, channel, amount, "
    "balance_before, destination_id, destination_type, new_destination, device_id, new_device, "
    "password_change_24h, sim_change_48h, ip_department, ip_department_mismatch, "
    "account_age_days, is_fraud, fraud_type, source) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'live') "
    "ON CONFLICT DO NOTHING",
    (
      tx["id"], tx["occurred_at"], tx["customer_id"], tx["operation_type"], tx["channel"],
      tx["amount"], tx["balance_before"], tx["destination_id"], tx["destination_type"],
      tx["new_destination"], tx.get("device_id"), tx["new_device"], tx["password_change_24h"],
      tx["sim_change_48h"], tx.get("ip_department"), tx["ip_department_mismatch"],
      tx["account_age_days"], bool(meta.get("is_fraud")), meta.get("fraud_type"),
    ),
  )
  cur.execute(
    "INSERT INTO decisions (id, transaction_id, score, action, hard_rule, reasons, features, "
    "rules, timings, latency_ms, model_version) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
    (
      message["decision_id"], tx["id"], decision["score"], decision["action"],
      decision.get("hard_rule"), json.dumps(decision["reasons"]),
      json.dumps(decision.get("features")), json.dumps(decision.get("rules")),
      json.dumps(decision.get("timings")), decision["latency_ms"], decision["model_version"],
    ),
  )
  if decision["action"] in ("hold", "reject"):
    cur.execute(
      "INSERT INTO alerts (decision_id) VALUES (%s) ON CONFLICT DO NOTHING",
      (message["decision_id"],),
    )

  persisted_at = datetime.now(timezone.utc)
  scored_at = datetime.fromisoformat(decision["scored_at"])
  lag_ms = round((persisted_at - scored_at).total_seconds() * 1000, 1)
  for event, actor, at, details in (
    (
      "scored", "api", scored_at,
      {"action": decision["action"], "score": decision["score"], "model": decision["model_version"]},
    ),
    (
      "persisted", "persister", persisted_at,
      {"topic": kafka["topic"], "partition": kafka["partition"], "offset": kafka["offset"],
       "lag_ms": lag_ms},
    ),
  ):
    cur.execute(
      "INSERT INTO audit_log (entity, entity_id, event, details, actor, occurred_at) "
      "VALUES ('decision', %s, %s, %s, %s, %s)",
      (message["decision_id"], event, json.dumps(details), actor, at),
    )
