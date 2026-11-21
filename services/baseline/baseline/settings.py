import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
INTERVAL_SECONDS = float(os.environ.get("BASELINE_INTERVAL_SECONDS", "30"))
BATCH_SIZE = 5000


def database_dsn() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )
