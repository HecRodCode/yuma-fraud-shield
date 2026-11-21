import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb
import yaml
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from .features import CHANNELS, MODEL_COLUMNS, SQL_FEATURES

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
TRAIN_FRACTION = 0.6
TARGET_HOLD_PRECISION = 0.98
MAX_FRAUD_PASSED = 0.005

DATASET_QUERY = """
  SELECT t.id, t.created_at, t.channel, t.is_fraud, t.fraud_type, f.*
  FROM transactions t
  CROSS JOIN LATERAL compute_features(
    t.source_account, t.target_account, t.amount, t.channel, t.device, t.created_at
  ) f
  ORDER BY t.created_at
"""


def dsn_from_env() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def load_dataset() -> pd.DataFrame:
  with psycopg.connect(dsn_from_env()) as conn, conn.cursor() as cur:
    cur.execute(DATASET_QUERY)
    columns = [c.name for c in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=columns)
  for channel in CHANNELS:
    df[f"channel_{channel}"] = (df["channel"] == channel).astype(float)
  df[SQL_FEATURES] = df[SQL_FEATURES].astype(float)
  return df


def pick_thresholds(y: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
  precision, _, thresholds = precision_recall_curve(y, scores)
  ok = np.where(precision[:-1] >= TARGET_HOLD_PRECISION)[0]
  high_min = float(thresholds[ok[0]]) if len(ok) else 0.5
  low_max = float(np.quantile(scores[y == 1], MAX_FRAUD_PASSED))
  return min(low_max, high_min), high_min


def report(val: pd.DataFrame, scores: np.ndarray, low_max: float, high_min: float) -> dict:
  y = val["is_fraud"].to_numpy().astype(int)
  hold = scores >= high_min
  challenge = (scores >= low_max) & ~hold
  approve = scores < low_max
  legit = y == 0

  metrics = {
    "roc_auc": float(roc_auc_score(y, scores)),
    "pr_auc": float(average_precision_score(y, scores)),
    "hold_count": int(hold.sum()),
    "hold_false_positive_rate": float(1 - y[hold].mean()) if hold.any() else 0.0,
    "challenge_rate_legit": float((challenge & legit).sum() / legit.sum()),
    "hold_rate_legit": float((hold & legit).sum() / legit.sum()),
    "fraud_approved": int((approve & (y == 1)).sum()),
    "fraud_total": int(y.sum()),
    "recall_by_type": {},
  }
  for kind, group in val[val["is_fraud"]].groupby("fraud_type"):
    caught = scores[group.index - val.index[0]] >= low_max
    metrics["recall_by_type"][kind] = float(caught.mean())
  return metrics


def main() -> None:
  df = load_dataset()
  print(f"dataset: {len(df)} rows, {int(df['is_fraud'].sum())} fraud")

  cut = int(len(df) * TRAIN_FRACTION)
  train, val = df.iloc[:cut], df.iloc[cut:]
  y_train = train["is_fraud"].astype(int)
  weight = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))

  model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.08,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=weight**0.5,
    eval_metric="aucpr",
    tree_method="hist",
    n_jobs=4,
  )
  model.fit(train[MODEL_COLUMNS], y_train)

  scores = model.predict_proba(val[MODEL_COLUMNS])[:, 1]
  low_max, high_min = pick_thresholds(val["is_fraud"].to_numpy().astype(int), scores)
  metrics = report(val, scores, low_max, high_min)

  version = "xgb-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
  ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
  model.get_booster().save_model(str(ARTIFACTS_DIR / "model.json"))
  meta = {
    "version": version,
    "features": MODEL_COLUMNS,
    "holdout_start": val["created_at"].iloc[0].isoformat(),
    "metrics": metrics,
  }
  (ARTIFACTS_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
  (CONFIG_DIR / "thresholds.yaml").write_text(
    yaml.safe_dump({"score": {"low_max": round(low_max, 5), "high_min": round(high_min, 5)}})
  )

  print(f"version: {version}")
  print(f"thresholds: low_max={low_max:.4f} high_min={high_min:.4f}")
  print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
  main()
