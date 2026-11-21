import math
import time
import uuid
from datetime import datetime, timezone

from psycopg_pool import ConnectionPool

from app.core.settings import DECISIONS_TOPIC
from app.domain.model import Scorer
from app.domain.reasons import RULE_REASONS, build_reasons
from app.domain.rules import RULE_ACTIONS
from app.infra.kafka import Publisher
from app.schemas.scoring import ScoreRequest, ScoreResponse
from shield_ml.features import FEATURES_QUERY, build_row


class ScoringService:
  def __init__(self, pool: ConnectionPool, scorer: Scorer, publisher: Publisher) -> None:
    self.pool = pool
    self.scorer = scorer
    self.publisher = publisher

  def score(self, req: ScoreRequest) -> ScoreResponse:
    started = time.perf_counter()
    self.scorer.refresh()

    at = req.occurred_at or datetime.now(timezone.utc)
    transaction_id = req.transaction_id or f"T-{uuid.uuid4().hex[:12]}"
    checks = self.scorer.rules.evaluate(req.destination_id, req.operation_type, req.amount)
    rule = next((c["rule"] for c in checks if c["fired"]), None)
    features = None
    timings: dict[str, float] = {}

    if rule:
      value = 1.0
      action = RULE_ACTIONS[rule]
      reasons = [
        {"feature": rule, "text": RULE_REASONS[rule], "effect": "raises_risk", "impact": 1.0}
      ]
    else:
      tx = {**req.model_dump(), "occurred_at": at}
      history = self._fetch_history(req, at)
      fetched = time.perf_counter()
      vector = build_row(tx, history)
      value, contributions = self.scorer.predict(vector)
      action = self.scorer.thresholds.decide(value)
      reasons = build_reasons(self.scorer.features, vector, contributions)
      features = {n: None if math.isnan(v) else v for n, v in zip(self.scorer.features, vector)}
      timings = {
        "features_ms": round((fetched - started) * 1000, 2),
        "model_ms": round((time.perf_counter() - fetched) * 1000, 2),
      }

    decision_id = uuid.uuid4()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    timings["total_ms"] = latency_ms
    value = round(value, 5)

    self.publisher.publish(
      DECISIONS_TOPIC,
      transaction_id,
      self._message(
        req, at, transaction_id, decision_id, value, action, rule, reasons, latency_ms,
        features, checks, timings,
      ),
    )

    return ScoreResponse(
      decision_id=decision_id,
      transaction_id=transaction_id,
      action=action,
      score=value,
      reasons=reasons,
      latency_ms=latency_ms,
      model_version=self.scorer.version,
    )

  def _fetch_history(self, req: ScoreRequest, at: datetime) -> dict:
    with self.pool.connection() as conn:
      return conn.execute(
        FEATURES_QUERY, (req.customer_id, req.destination_id, req.device_id, at)
      ).fetchone()

  def _message(
    self,
    req: ScoreRequest,
    at: datetime,
    transaction_id: str,
    decision_id: uuid.UUID,
    score: float,
    action: str,
    rule: str | None,
    reasons: list[dict],
    latency_ms: float,
    features: dict | None,
    checks: list[dict],
    timings: dict,
  ) -> dict:
    transaction = req.model_dump(exclude={"meta", "transaction_id", "occurred_at"})
    return {
      "decision_id": str(decision_id),
      "transaction": {"id": transaction_id, "occurred_at": at.isoformat(), **transaction},
      "decision": {
        "score": score,
        "action": action,
        "hard_rule": rule,
        "reasons": reasons,
        "features": features,
        "rules": checks,
        "timings": timings,
        "latency_ms": latency_ms,
        "model_version": self.scorer.version,
        "scored_at": datetime.now(timezone.utc).isoformat(),
      },
      "meta": req.meta,
    }
