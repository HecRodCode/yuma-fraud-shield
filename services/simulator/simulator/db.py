import os

import psycopg

from .models import Batch

TABLES = (
  "alerts, labels, decisions, baseline_decisions, "
  "transactions, session_events, accounts"
)


def dsn_from_env() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def write_batch(dsn: str, batch: Batch, reset: bool) -> None:
  with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    if reset:
      cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    else:
      cur.execute("SELECT count(*) FROM accounts")
      if cur.fetchone()[0] > 0:
        raise SystemExit("accounts table is not empty, use --reset to overwrite")

    with cur.copy("COPY accounts (id, created_at, is_merchant) FROM STDIN") as copy:
      for a in batch.accounts:
        copy.write_row((a.id, a.created_at, a.is_merchant))

    with cur.copy(
      "COPY session_events (id, account_id, type, device, occurred_at) FROM STDIN"
    ) as copy:
      for e in batch.events:
        copy.write_row((e.id, e.account_id, e.type, e.device, e.occurred_at))

    with cur.copy(
      "COPY transactions (id, source_account, target_account, amount, channel, "
      "device, created_at, is_fraud, fraud_type) FROM STDIN"
    ) as copy:
      for t in batch.transactions:
        copy.write_row(
          (t.id, t.source_account, t.target_account, t.amount, t.channel,
           t.device, t.created_at, t.is_fraud, t.fraud_type)
        )
