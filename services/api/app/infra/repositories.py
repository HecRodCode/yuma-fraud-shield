import json


def ensure_account(cur, account_id: str, at: str) -> None:
  cur.execute(
    "INSERT INTO accounts (id, created_at) VALUES (%s, %s) ON CONFLICT DO NOTHING",
    (account_id, at),
  )


def save_session_event(cur, event: dict) -> None:
  ensure_account(cur, event["account_id"], event["occurred_at"])
  cur.execute(
    "INSERT INTO session_events (id, account_id, type, device, occurred_at) "
    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
    (event["id"], event["account_id"], event["type"], event.get("device"), event["occurred_at"]),
  )


def save_decision(cur, message: dict) -> None:
  tx = message["transaction"]
  decision = message["decision"]
  meta = message.get("meta") or {}

  ensure_account(cur, tx["source_account"], tx["created_at"])
  ensure_account(cur, tx["target_account"], tx["created_at"])
  cur.execute(
    "INSERT INTO transactions (id, source_account, target_account, amount, channel, device, "
    "created_at, is_fraud, fraud_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING",
    (
      tx["id"], tx["source_account"], tx["target_account"], tx["amount"], tx["channel"],
      tx.get("device"), tx["created_at"], bool(meta.get("is_fraud")), meta.get("fraud_type"),
    ),
  )
  cur.execute(
    "INSERT INTO decisions (id, transaction_id, score, action, hard_rule, reasons, "
    "latency_ms, model_version) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
    (
      message["decision_id"], tx["id"], decision["score"], decision["action"],
      decision.get("hard_rule"), json.dumps(decision["reasons"]), decision["latency_ms"],
      decision["model_version"],
    ),
  )
  if decision["action"] == "hold":
    cur.execute(
      "INSERT INTO alerts (decision_id) VALUES (%s) ON CONFLICT DO NOTHING",
      (message["decision_id"],),
    )
  cur.execute(
    "INSERT INTO audit_log (entity, entity_id, event, details, actor) "
    "VALUES ('decision', %s, 'scored', %s, 'api')",
    (message["decision_id"], json.dumps({"action": decision["action"], "score": decision["score"]})),
  )
