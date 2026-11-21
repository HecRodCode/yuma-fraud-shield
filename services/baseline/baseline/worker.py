import json
import logging
import time
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from baseline.rules import StaticRules, load_rules
from baseline.settings import BATCH_SIZE, CONFIG_DIR, INTERVAL_SECONDS, database_dsn

log = logging.getLogger("baseline")

PENDING_QUERY = """
  SELECT
    t.id,
    t.operation_type,
    t.amount::FLOAT8 AS amount,
    t.balance_before::FLOAT8 AS balance_before,
    t.new_destination,
    t.new_device,
    t.password_change_24h,
    t.sim_change_48h,
    t.ip_department_mismatch,
    t.account_age_days,
    t.occurred_at,
    EXTRACT(HOUR FROM t.occurred_at AT TIME ZONE 'America/Bogota')::INT AS hour_of_day,
    (
      SELECT count(*) FROM transactions p
      WHERE p.customer_id = t.customer_id
        AND p.operation_type IN ('instant_transfer', 'correspondent_withdrawal', 'atm_withdrawal')
        AND p.occurred_at > t.occurred_at - INTERVAL '60 minutes'
        AND (p.occurred_at, p.id) <= (t.occurred_at, t.id)
    ) AS outflows_60m,
    (
      SELECT COALESCE(sum(p.amount), 0)::FLOAT8 FROM transactions p
      WHERE p.customer_id = t.customer_id
        AND p.operation_type IN ('instant_transfer', 'correspondent_withdrawal', 'atm_withdrawal')
        AND p.occurred_at >= t.occurred_at - INTERVAL '1 day'
        AND (p.occurred_at, p.id) <= (t.occurred_at, t.id)
        AND (p.occurred_at AT TIME ZONE 'America/Bogota')::DATE
          = (t.occurred_at AT TIME ZONE 'America/Bogota')::DATE
    ) AS daily_total
  FROM transactions t
  WHERE NOT EXISTS (SELECT 1 FROM baseline_decisions b WHERE b.transaction_id = t.id)
  ORDER BY t.occurred_at, t.id
  LIMIT %(limit)s
"""

INSERT_QUERY = (
  "INSERT INTO baseline_decisions (transaction_id, action, rules_fired, details, detected_at) "
  "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
)


def batch_end(created_at: datetime, minutes: int) -> datetime:
  step = minutes * 60
  epoch = created_at.timestamp()
  return datetime.fromtimestamp((epoch // step + 1) * step, tz=timezone.utc)


def process_pending(conn: psycopg.Connection, rules: StaticRules) -> int:
  total = 0
  while True:
    rows = conn.execute(PENDING_QUERY, {"limit": BATCH_SIZE}).fetchall()
    if not rows:
      return total
    decisions = []
    for row in rows:
      fired, severity = rules.evaluate(row)
      details = {
        "fired": fired,
        "severity": severity,
        "variables": {
          "hour_of_day": row["hour_of_day"],
          "outflows_60m": row["outflows_60m"],
          "daily_total": row["daily_total"],
        },
      }
      decisions.append(
        (
          row["id"],
          "alert" if fired else "approve",
          "|".join(fired) or None,
          json.dumps(details),
          batch_end(row["occurred_at"], rules.batch_minutes),
        )
      )
    with conn.cursor() as cur:
      cur.executemany(INSERT_QUERY, decisions)
    conn.commit()
    total += len(rows)
    log.info("evaluated %s transactions", total)


def run_forever() -> None:
  logging.basicConfig(level=logging.INFO)
  while True:
    rules = load_rules(CONFIG_DIR / "baseline_rules.yaml")
    with psycopg.connect(database_dsn(), row_factory=dict_row) as conn:
      process_pending(conn, rules)
    time.sleep(INTERVAL_SECONDS)
