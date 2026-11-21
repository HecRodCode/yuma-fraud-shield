from datetime import datetime

import psycopg

from simulator.domain.models import Customer


def virtual_now(dsn: str) -> datetime:
  with psycopg.connect(dsn) as conn:
    return conn.execute("SELECT max(occurred_at) FROM transactions").fetchone()[0]


def departments(dsn: str) -> list[str]:
  with psycopg.connect(dsn) as conn:
    rows = conn.execute("SELECT DISTINCT department FROM customers WHERE department IS NOT NULL")
    return [r[0] for r in rows.fetchall()]


def load_customers(dsn: str) -> dict[str, Customer]:
  with psycopg.connect(dsn) as conn:
    customers = {
      r[0]: Customer(id=r[0], joined_on=r[1], is_mule=r[2])
      for r in conn.execute("SELECT id, joined_on, confirmed_mule FROM customers").fetchall()
    }
    for clause in ("TRUE", "NOT is_fraud"):
      latest = conn.execute(
        "SELECT DISTINCT ON (customer_id) customer_id, device_id, ip_department, balance_before "
        f"FROM transactions WHERE {clause} ORDER BY customer_id, occurred_at DESC"
      ).fetchall()
      for cid, device, ip, balance in latest:
        c = customers[cid]
        c.usual_device, c.usual_ip, c.balance = device, ip, float(balance)
      stats = conn.execute(
        f"SELECT customer_id, avg(amount), count(*) FROM transactions WHERE {clause} GROUP BY 1"
      ).fetchall()
      for cid, avg_amount, n in stats:
        customers[cid].avg_amount, customers[cid].n_tx = float(avg_amount), n
    pairs = conn.execute(
      "SELECT customer_id, destination_id, destination_type FROM transactions "
      "WHERE NOT is_fraud AND operation_type IN ('instant_transfer', 'qr_payment') "
      "GROUP BY 1, 2, 3"
    ).fetchall()
    for cid, dest, dtype in pairs:
      c = customers[cid]
      (c.merchants if dtype == "merchant" else c.contacts).append((dest, dtype))
  return {k: c for k, c in customers.items() if c.usual_device}
