import psycopg

from simulator.domain.models import Account, Batch

TABLES = (
  "alerts, labels, decisions, baseline_decisions, "
  "transactions, session_events, accounts"
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


def load_population(dsn: str) -> list[Account]:
  accounts: dict[str, Account] = {}
  with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, created_at, is_merchant FROM accounts")
    for id_, created_at, is_merchant in cur.fetchall():
      accounts[id_] = Account(id=id_, created_at=created_at, is_merchant=is_merchant)

    cur.execute(
      "SELECT source_account, avg(amount), count(*), array_agg(DISTINCT device) "
      "FROM transactions WHERE NOT is_fraud GROUP BY 1"
    )
    for id_, avg_amount, n, devices in cur.fetchall():
      acc = accounts[id_]
      acc.avg_amount = float(avg_amount)
      acc.daily_rate = float(n)
      acc.devices = [d for d in devices if d]

    cur.execute(
      "SELECT DISTINCT t.source_account, t.target_account, a.is_merchant "
      "FROM transactions t JOIN accounts a ON a.id = t.target_account "
      "WHERE NOT t.is_fraud AND t.channel IN ('transfer', 'qr', 'bill_payment')"
    )
    for source, target, is_merchant in cur.fetchall():
      acc = accounts[source]
      (acc.favorite_merchants if is_merchant else acc.contacts).append(target)

  return list(accounts.values())


def insert_accounts(dsn: str, accounts: list[Account]) -> None:
  with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    for a in accounts:
      cur.execute(
        "INSERT INTO accounts (id, created_at, is_merchant) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (a.id, a.created_at, a.is_merchant),
      )
