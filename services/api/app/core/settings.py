import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:29092")

SESSION_TOPIC = "session-events"
DECISIONS_TOPIC = "decisions"


def database_dsn() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )
