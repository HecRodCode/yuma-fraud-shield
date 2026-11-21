import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb
import yaml
from psycopg.rows import dict_row
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from shield_ml.fairness import audit
from shield_ml.features import MODEL_COLUMNS, build_row

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
VALIDATION_START = pd.Timestamp("2026-09-01", tz="America/Bogota")
TEST_START = pd.Timestamp("2026-10-01", tz="America/Bogota")
HOLD_PRECISION = 0.70
REJECT_PRECISION = 0.95
FRICTION_BUDGET = 0.03

DATASET_QUERY = """
  SELECT
    t.id, t.occurred_at, t.operation_type, t.channel, t.amount, t.balance_before,
    t.destination_type, t.new_destination, t.new_device, t.password_change_24h,
    t.sim_change_48h, t.ip_department_mismatch, t.account_age_days, t.is_fraud, t.fraud_type,
    c.department, c.age_range, f.*
  FROM transactions t
  JOIN customers c ON c.id = t.customer_id
  CROSS JOIN LATERAL compute_features(
    t.customer_id, t.destination_id, t.device_id, t.occurred_at
  ) f
  WHERE t.source = 'dataset'
  ORDER BY t.occurred_at, t.id
"""


def dsn_from_env() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def load_dataset() -> tuple[pd.DataFrame, np.ndarray]:
  with psycopg.connect(dsn_from_env(), row_factory=dict_row) as conn:
    rows = conn.execute(DATASET_QUERY).fetchall()
  matrix = np.array([build_row(r, r) for r in rows])
  df = pd.DataFrame(rows)[
    ["id", "occurred_at", "amount", "is_fraud", "fraud_type", "department", "age_range"]
  ]
  df["amount"] = df["amount"].astype(float)
  return df, matrix


def pick_thresholds(y: np.ndarray, scores: np.ndarray) -> tuple[float, float, float]:
  precision, _, thresholds = precision_recall_curve(y, scores)

  def at_precision(target: float) -> float:
    ok = np.where(precision[:-1] >= target)[0]
    return float(thresholds[ok[0]]) if len(ok) else 0.99

  high_min = at_precision(HOLD_PRECISION)
  reject_min = max(at_precision(REJECT_PRECISION), high_min)
  low_max = float(np.quantile(scores[y == 0], 1 - FRICTION_BUDGET))
  return min(low_max, high_min), high_min, reject_min


def decide(scores: np.ndarray, low_max: float, high_min: float, reject_min: float) -> np.ndarray:
  return np.select(
    [scores >= reject_min, scores >= high_min, scores >= low_max],
    ["reject", "hold", "challenge"],
    default="approve",
  )


def report(df: pd.DataFrame, scores: np.ndarray, actions: np.ndarray) -> dict:
  fraud = df["is_fraud"].to_numpy()
  flagged = actions != "approve"
  blocked = np.isin(actions, ["hold", "reject"])
  vp = int((flagged & fraud).sum())
  fp = int((blocked & ~fraud).sum())
  y = fraud.astype(int)
  result = {
    "transactions": int(len(df)),
    "fraud_cases": int(fraud.sum()),
    "roc_auc": float(roc_auc_score(y, scores)),
    "pr_auc": float(average_precision_score(y, scores)),
    "fraud_detected_pct": round(100 * vp / fraud.sum(), 2),
    "false_positive_pct": round(100 * fp / max(vp + fp, 1), 2),
    "legit_blocked_pct": round(100 * fp / (~fraud).sum(), 2),
    "legit_challenged_pct": round(100 * (actions[~fraud] == "challenge").mean(), 2),
    "fraud_amount_protected_pct": round(
      100 * df.loc[flagged & fraud, "amount"].sum() / df.loc[fraud, "amount"].sum(), 2
    ),
    "actions": {a: int((actions == a).sum()) for a in ("approve", "challenge", "hold", "reject")},
    "detected_by_type": {},
  }
  for kind, part in df[df["is_fraud"]].groupby("fraud_type"):
    result["detected_by_type"][kind] = {
      "cases": int(len(part)),
      "detected_pct": round(100 * (actions[part.index] != "approve").mean(), 2),
    }
  return result


def main() -> None:
  df, matrix = load_dataset()
  print(f"dataset: {len(df)} rows, {int(df['is_fraud'].sum())} fraud", flush=True)

  train = (df["occurred_at"] < VALIDATION_START).to_numpy()
  val = ((df["occurred_at"] >= VALIDATION_START) & (df["occurred_at"] < TEST_START)).to_numpy()
  test = (df["occurred_at"] >= TEST_START).to_numpy()
  y = df["is_fraud"].to_numpy().astype(int)
  weight = float((y[train] == 0).sum() / max(1, (y[train] == 1).sum()))

  model = xgb.XGBClassifier(
    n_estimators=400,
    max_depth=5,
    learning_rate=0.06,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=3,
    scale_pos_weight=weight**0.5,
    eval_metric="aucpr",
    tree_method="hist",
    n_jobs=4,
  )
  model.fit(pd.DataFrame(matrix[train], columns=MODEL_COLUMNS), y[train])

  predict = lambda mask: model.predict_proba(pd.DataFrame(matrix[mask], columns=MODEL_COLUMNS))[:, 1]
  val_scores, test_scores = predict(val), predict(test)
  low_max, high_min, reject_min = pick_thresholds(y[val], val_scores)

  test_df = df[test].reset_index(drop=True)
  actions = decide(test_scores, low_max, high_min, reject_min)
  metrics = {
    "validation": report(df[val].reset_index(drop=True), val_scores,
                         decide(val_scores, low_max, high_min, reject_min)),
    "test": report(test_df, test_scores, actions),
  }
  fairness = audit(test_df, actions)

  booster = model.get_booster()
  contribs = booster.predict(
    xgb.DMatrix(pd.DataFrame(matrix[test], columns=MODEL_COLUMNS)), pred_contribs=True
  )[:, :-1]
  importance = sorted(
    zip(MODEL_COLUMNS, np.abs(contribs).mean(axis=0).round(4).tolist()), key=lambda p: -p[1]
  )[:15]

  version = "xgb-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
  ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
  booster.save_model(str(ARTIFACTS_DIR / "model.json"))
  meta = {
    "version": version,
    "features": MODEL_COLUMNS,
    "holdout_start": TEST_START.isoformat(),
    "splits": {"validation_start": VALIDATION_START.isoformat(), "test_start": TEST_START.isoformat()},
    "metrics": metrics,
    "top_features": importance,
  }
  (ARTIFACTS_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
  (ARTIFACTS_DIR / "fairness.json").write_text(json.dumps(fairness, indent=2))
  (CONFIG_DIR / "thresholds.yaml").write_text(
    yaml.safe_dump(
      {"score": {"low_max": round(low_max, 5), "high_min": round(high_min, 5),
                 "reject_min": round(reject_min, 5)}}
    )
  )

  print(f"version: {version}")
  print(f"thresholds: low_max={low_max:.4f} high_min={high_min:.4f} reject_min={reject_min:.4f}")
  print(json.dumps(metrics["test"], indent=2))
  print("top features:", importance[:8])
  print("fairness gaps:", {k: (v["legit_blocked_max_min_gap_pp"], v["legit_flagged_max_min_gap_pp"]) for k, v in fairness.items()})


if __name__ == "__main__":
  main()
