import json
import os
import shutil
from pathlib import Path

import psycopg
import yaml

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))

MAX_DETECTION_DROP_PP = 1.0
MAX_FALSE_POSITIVE_RISE_PP = 5.0
MAX_LEGIT_BLOCKED_RISE_PP = 0.5


def dsn() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def write_atomic(path: Path, content: str) -> None:
  temporary = path.with_name(path.name + ".tmp")
  temporary.write_text(content)
  os.replace(temporary, path)


def version_dir(version: str) -> Path:
  return ARTIFACTS_DIR / "models" / version


def active_metrics() -> dict | None:
  with psycopg.connect(dsn()) as conn:
    row = conn.execute("SELECT metrics FROM model_versions WHERE status = 'active'").fetchone()
  return row[0] if row else None


def evaluate_gate(candidate: dict, current: dict | None) -> dict:
  if current is None:
    return {"passed": True, "reason": "no active model to compare with"}
  new = {k: float(candidate[k]) for k in ("fraud_detected_pct", "false_positive_pct", "legit_blocked_pct")}
  old = {k: float(current[k]) for k in new}
  checks = {
    "fraud_detected_pct": new["fraud_detected_pct"] >= old["fraud_detected_pct"] - MAX_DETECTION_DROP_PP,
    "false_positive_pct": new["false_positive_pct"] <= old["false_positive_pct"] + MAX_FALSE_POSITIVE_RISE_PP,
    "legit_blocked_pct": new["legit_blocked_pct"] <= old["legit_blocked_pct"] + MAX_LEGIT_BLOCKED_RISE_PP,
  }
  return {"passed": all(checks.values()), "checks": checks, "candidate": new, "active": old}


def publish(version: str) -> None:
  source = version_dir(version)
  meta = json.loads((source / "meta.json").read_text())
  write_atomic(ARTIFACTS_DIR / "meta.json", json.dumps(meta, indent=2))
  if (source / "fairness.json").exists():
    shutil.copyfile(source / "fairness.json", ARTIFACTS_DIR / "fairness.json")
  write_atomic(CONFIG_DIR / "thresholds.yaml", yaml.safe_dump({"score": meta["thresholds"]}))
  shutil.copyfile(source / "model.json", ARTIFACTS_DIR / "model.json.tmp")
  os.replace(ARTIFACTS_DIR / "model.json.tmp", ARTIFACTS_DIR / "model.json")


def promote(version: str, actor: str = "trainer") -> None:
  publish(version)
  with psycopg.connect(dsn()) as conn:
    conn.execute("UPDATE model_versions SET status = 'superseded' WHERE status = 'active'")
    conn.execute("UPDATE model_versions SET status = 'active' WHERE version = %s", (version,))
    conn.execute(
      "INSERT INTO audit_log (entity, entity_id, event, details, actor) "
      "VALUES ('model', %s, 'promoted', '{}', %s)",
      (version, actor),
    )
