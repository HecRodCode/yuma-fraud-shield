import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb
from psycopg.rows import dict_row
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from shield_ml.fairness import audit
from shield_ml.registry import ARTIFACTS_DIR, CONFIG_DIR, active_metrics, evaluate_gate, promote, version_dir
from shield_ml.features import MODEL_COLUMNS, build_row

VALIDATION_START = pd.Timestamp("2026-09-01", tz="America/Bogota")
TEST_START = pd.Timestamp("2026-10-01", tz="America/Bogota")
HOLD_PRECISION = 0.70
REJECT_PRECISION = 0.95
FRICTION_BUDGET = 0.03
FEEDBACK_WEIGHT = float(os.environ.get("FEEDBACK_WEIGHT", "2"))

DATASET_QUERY = """
  SELECT
    t.id, t.occurred_at, t.operation_type, t.channel, t.amount, t.balance_before,
    t.destination_type, t.new_destination, t.new_device, t.password_change_24h,
    t.sim_change_48h, t.ip_department_mismatch, t.account_age_days, t.is_fraud, t.fraud_type,
    t.source, l.verdict, c.department, c.age_range, f.*
  FROM transactions t
  JOIN customers c ON c.id = t.customer_id
  LEFT JOIN labels l ON l.transaction_id = t.id
  CROSS JOIN LATERAL compute_features(
    t.customer_id, t.destination_id, t.device_id, t.occurred_at
  ) f
  WHERE t.source = 'dataset'
     OR (
       %(feedback)s AND (
         l.id IS NOT NULL
         OR EXISTS (
           SELECT 1 FROM decisions d
           WHERE d.transaction_id = t.id AND d.action IN ('approve', 'challenge')
         )
       )
     )
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


def load_dataset(use_feedback: bool) -> tuple[pd.DataFrame, np.ndarray]:
  with psycopg.connect(dsn_from_env(), row_factory=dict_row) as conn:
    rows = conn.execute(DATASET_QUERY, {"feedback": use_feedback}).fetchall()
  matrix = np.array([build_row(r, r) for r in rows])
  df = pd.DataFrame(rows)[
    ["id", "occurred_at", "amount", "is_fraud", "fraud_type", "source", "verdict",
     "department", "age_range"]
  ]
  df["amount"] = df["amount"].astype(float)
  return df, matrix


def training_labels(df: pd.DataFrame, use_feedback: bool) -> tuple[np.ndarray, np.ndarray, dict]:
  dataset = (df["source"] == "dataset").to_numpy()
  labelled = df["verdict"].notna().to_numpy()
  in_test_period = (df["occurred_at"] >= TEST_START).to_numpy()
  eligible = labelled & (~dataset | ~in_test_period) & use_feedback

  y = df["is_fraud"].to_numpy().astype(int)
  y[~dataset] = 0
  y[eligible] = (df.loc[eligible, "verdict"] == "fraud").astype(int).to_numpy()

  weights = np.ones(len(df))
  weights[eligible] = FEEDBACK_WEIGHT
  summary = {
    "labels_used": int(eligible.sum()),
    "labels_fraud": int((eligible & (y == 1)).sum()),
    "labels_legitimate": int((eligible & (y == 0)).sum()),
    "labels_ignored_test_period": int((labelled & dataset & in_test_period).sum()),
    "assumed_legitimate": int((~dataset & ~eligible).sum()),
  }
  return y, weights, summary


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


def register_version(version: str, trigger: str, use_feedback: bool, feedback: dict,
                     thresholds: dict, metrics: dict, gate: dict, status: str) -> None:
  with psycopg.connect(dsn_from_env()) as conn:
    conn.execute(
      "INSERT INTO model_versions "
      "(version, trigger, use_feedback, feedback, thresholds, metrics, gate, status) "
      "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
      (version, trigger, use_feedback, json.dumps(feedback), json.dumps(thresholds),
       json.dumps(metrics), json.dumps(gate), status),
    )
    conn.execute(
      "INSERT INTO audit_log (entity, entity_id, event, details, actor) "
      "VALUES ('model', %s, %s, %s, 'trainer')",
      (version, "trained" if status != "rejected" else "rejected",
       json.dumps({"trigger": trigger, "feedback": feedback, "gate": gate})),
    )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--no-feedback", action="store_true")
  parser.add_argument("--trigger", default="manual")
  parser.add_argument("--force", action="store_true", help="publish even if the gate fails")
  args = parser.parse_args()
  use_feedback = not args.no_feedback

  df, matrix = load_dataset(use_feedback)
  y, weights, feedback = training_labels(df, use_feedback)
  dataset = (df["source"] == "dataset").to_numpy()
  print(f"rows: {len(df)} ({int(dataset.sum())} dataset) feedback: {feedback}", flush=True)

  before_val = (df["occurred_at"] < VALIDATION_START).to_numpy()
  in_val = ((df["occurred_at"] >= VALIDATION_START) & (df["occurred_at"] < TEST_START)).to_numpy()
  train = (before_val & dataset) | ~dataset
  val = in_val & dataset
  test = (df["occurred_at"] >= TEST_START).to_numpy() & dataset
  truth = df["is_fraud"].to_numpy().astype(int)
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
  frame = lambda mask: pd.DataFrame(matrix[mask], columns=MODEL_COLUMNS)
  model.fit(frame(train), y[train], sample_weight=weights[train])

  val_scores = model.predict_proba(frame(val))[:, 1]
  test_scores = model.predict_proba(frame(test))[:, 1]
  low_max, high_min, reject_min = pick_thresholds(truth[val], val_scores)

  val_df = df[val].reset_index(drop=True)
  test_df = df[test].reset_index(drop=True)
  actions = decide(test_scores, low_max, high_min, reject_min)
  metrics = {
    "validation": report(val_df, val_scores, decide(val_scores, low_max, high_min, reject_min)),
    "test": report(test_df, test_scores, actions),
  }
  fairness = audit(test_df, actions)

  booster = model.get_booster()
  contribs = booster.predict(xgb.DMatrix(frame(test)), pred_contribs=True)[:, :-1]
  importance = sorted(
    zip(MODEL_COLUMNS, np.abs(contribs).mean(axis=0).round(4).tolist()), key=lambda p: -p[1]
  )[:15]

  version = "xgb-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
  thresholds = {"low_max": round(low_max, 5), "high_min": round(high_min, 5),
                "reject_min": round(reject_min, 5)}
  meta = {
    "version": version,
    "features": MODEL_COLUMNS,
    "holdout_start": TEST_START.isoformat(),
    "splits": {"validation_start": VALIDATION_START.isoformat(), "test_start": TEST_START.isoformat()},
    "use_feedback": use_feedback,
    "feedback": feedback,
    "thresholds": thresholds,
    "metrics": metrics,
    "top_features": importance,
  }

  history = version_dir(version)
  history.mkdir(parents=True, exist_ok=True)
  booster.save_model(str(history / "model.json"))
  (history / "meta.json").write_text(json.dumps(meta, indent=2))
  (history / "fairness.json").write_text(json.dumps(fairness, indent=2))

  gate = evaluate_gate(metrics["test"], active_metrics())
  gate["checks"] = {k: bool(v) for k, v in gate.get("checks", {}).items()}
  publish_it = gate["passed"] or args.force
  register_version(version, args.trigger, use_feedback, feedback, thresholds, metrics["test"],
                   gate, "superseded" if publish_it else "rejected")
  if publish_it:
    promote(version)

  print(f"version: {version}  gate passed: {gate['passed']}  published: {publish_it}")
  print(f"thresholds: {thresholds}")
  print(json.dumps(gate, indent=2))
  print(json.dumps(metrics["test"], indent=2))
  print("top features:", importance[:8])


if __name__ == "__main__":
  main()
