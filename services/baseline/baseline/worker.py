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
    t.channel,
    t.amount::FLOAT8 AS amount,
    t.created_at,
    EXTRACT(HOUR FROM t.created_at AT TIME ZONE 'America/Bogota')::INT AS hour_of_day,
    (
      SELECT COALESCE(sum(p.amount), 0)::FLOAT8 FROM transactions p
      WHERE p.source_account = t.source_account
        AND p.created_at > t.created_at - INTERVAL '24 hours'
        AND p.created_at <= t.created_at
    ) AS day_total,
    (
      t.target_account <> 'sys_cashpoint' AND EXISTS (
        SELECT 1 FROM transactions f
        WHERE f.target_account = t.target_account
          AND f.is_fraud
          AND f.created_at + make_interval(hours => %(delay)s) <= t.created_at
      )
    ) AS restricted_target
  FROM transactions t
  WHERE NOT EXISTS (SELECT 1 FROM baseline_decisions b WHERE b.transaction_id = t.id)
  ORDER BY t.created_at
  LIMIT %(limit)s
"""

INSERT_QUERY = (
  "INSERT INTO baseline_decisions (transaction_id, action, rule, details, detected_at) "
  "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
)


def batch_end(created_at: datetime, minutes: int) -> datetime:
  step = minutes * 60
  epoch = created_at.timestamp()
  return datetime.fromtimestamp((epoch // step + 1) * step, tz=timezone.utc)


def process_pending(conn: psycopg.Connection, rules: StaticRules) -> int:
  total = 0
  while True:
    rows = conn.execute(
      PENDING_QUERY, {"delay": rules.restricted_delay_hours, "limit": BATCH_SIZE}
    ).fetchall()
    if not rows:
      return total
    decisions = []
    for row in rows:
      rule, checks = rules.evaluate(row)
      decisions.append(
        (
          row["id"],
          "alert" if rule else "approve",
          rule,
          json.dumps({"checks": checks}),
          batch_end(row["created_at"], rules.batch_minutes),
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
