import json
import logging
import math
import uuid

import numpy as np
import psycopg
import xgboost as xgb
from psycopg.rows import dict_row

from app.core.settings import ARTIFACTS_DIR, database_dsn
from app.domain.model import ModelNotReadyError, Scorer
from app.domain.reasons import RULE_REASONS, build_reasons
from shield_ml.features import to_vector

log = logging.getLogger("replay")

PENDING_QUERY = """
  SELECT t.id, t.channel, t.amount::FLOAT8 AS amount, t.target_account, t.created_at, f.*
  FROM transactions t
  CROSS JOIN LATERAL compute_features(
    t.source_account, t.target_account, t.amount, t.channel, t.device, t.created_at
  ) f
  WHERE t.created_at >= %s
    AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.transaction_id = t.id)
  ORDER BY t.created_at
"""

CLEAR_QUERIES = (
  "DELETE FROM labels WHERE alert_id IN ("
  "  SELECT a.id FROM alerts a JOIN decisions d ON d.id = a.decision_id WHERE d.source = 'replay')",
  "DELETE FROM alerts WHERE decision_id IN (SELECT id FROM decisions WHERE source = 'replay')",
  "DELETE FROM decisions WHERE source = 'replay'",
)


def run_replay(scorer: Scorer, replay_all: bool = False) -> dict:
  if not scorer.ready:
    raise ModelNotReadyError("model not loaded, run training first")
  meta = json.loads((ARTIFACTS_DIR / "meta.json").read_text())
  start = "1970-01-01T00:00:00+00:00" if replay_all else meta["holdout_start"]

  with psycopg.connect(database_dsn(), row_factory=dict_row) as conn:
    for query in CLEAR_QUERIES:
      conn.execute(query)
    rows = conn.execute(PENDING_QUERY, (start,)).fetchall()
    log.info("scoring %s transactions", len(rows))
    if not rows:
      return {"decisions": 0, "alerts": 0, "model": scorer.version}

    vectors = np.array([to_vector(r, r["channel"]) for r in rows])
    matrix = xgb.DMatrix(vectors, feature_names=scorer.features, missing=math.nan)
    contribs = scorer.booster.predict(matrix, pred_contribs=True)
    scores = 1.0 / (1.0 + np.exp(-contribs.sum(axis=1)))

    decisions, alerts = [], []
    for i, row in enumerate(rows):
      checks = scorer.rules.evaluate(row["target_account"], row["channel"], row["amount"])
      rule = next((c["rule"] for c in checks if c["fired"]), None)
      features = None
      if rule:
        score, action = 1.0, "hold"
        reasons = [
          {"feature": rule, "text": RULE_REASONS[rule], "effect": "raises_risk", "impact": 1.0}
        ]
      else:
        score = float(scores[i])
        action = scorer.thresholds.decide(score)
        reasons = build_reasons(
          scorer.features, vectors[i].tolist(), contribs[i][:-1].tolist()
        )
        features = {
          name: None if math.isnan(v) else v for name, v in zip(scorer.features, vectors[i].tolist())
        }
      decision_id = uuid.uuid4()
      decisions.append(
        (
          decision_id, row["id"], round(score, 5), action, rule, json.dumps(reasons),
          json.dumps(features), json.dumps(checks), None, scorer.version, "replay",
          row["created_at"],
        )
      )
      if action == "hold":
        alerts.append((decision_id, row["created_at"]))

    with conn.cursor() as cur:
      with cur.copy(
        "COPY decisions (id, transaction_id, score, action, hard_rule, reasons, features, rules, "
        "latency_ms, model_version, source, created_at) FROM STDIN"
      ) as copy:
        for d in decisions:
          copy.write_row(d)
      with cur.copy("COPY alerts (decision_id, created_at) FROM STDIN") as copy:
        for a in alerts:
          copy.write_row(a)
      cur.execute(
        "INSERT INTO audit_log (entity, event, details, actor) VALUES ('replay', 'scored', %s, 'replay')",
        (json.dumps({"decisions": len(decisions), "alerts": len(alerts), "model": scorer.version}),),
      )
    conn.commit()
    log.info("stored %s decisions and %s alerts", len(decisions), len(alerts))
  return {"decisions": len(decisions), "alerts": len(alerts), "model": scorer.version}


def main() -> None:
  logging.basicConfig(level=logging.INFO)
  run_replay(Scorer())


if __name__ == "__main__":
  main()
