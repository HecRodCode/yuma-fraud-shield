import json
import os
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "/artifacts"))
SHIELD_COLOR = "#3987e5"
BASELINE_COLOR = "#d95926"


def dsn() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def query(sql: str, params=None) -> pd.DataFrame:
  with psycopg.connect(dsn(), row_factory=dict_row) as conn:
    return pd.DataFrame(conn.execute(sql, params).fetchall())


def rows(sql: str, params=None) -> list[dict]:
  with psycopg.connect(dsn(), row_factory=dict_row) as conn:
    return conn.execute(sql, params).fetchall()


def execute(statements: list[tuple[str, tuple]]) -> None:
  with psycopg.connect(dsn()) as conn:
    for sql, params in statements:
      conn.execute(sql, params)


def load_json(name: str) -> dict | None:
  path = ARTIFACTS_DIR / name
  return json.loads(path.read_text()) if path.exists() else None


def pct(numerator: float, denominator: float) -> float | None:
  return round(100 * numerator / denominator, 1) if denominator else None


def show(value: float | None, suffix: str = " %") -> str:
  return "n/a" if value is None else f"{value:,.1f}{suffix}"
