from datetime import datetime, timedelta

import numpy as np

from .fraud import (
  AVG_FRAUD_TX_PER_SCENARIO,
  FRAUD_TYPES,
  SCENARIO_WEIGHTS,
  SCENARIOS,
  Context,
)
from .legit import generate_legit
from .models import Batch
from .population import build_population


def build_history(
  rng: np.random.Generator,
  n_accounts: int,
  days: int,
  fraud_rate: float,
  end: datetime,
) -> Batch:
  start = end - timedelta(days=days)
  accounts = build_population(rng, n_accounts, start, end)

  batch = Batch(accounts=list(accounts))
  batch.extend(generate_legit(rng, accounts, start, end))

  ctx = Context(
    rng=rng,
    victims=[a for a in accounts if a.devices and not a.is_merchant],
    merchants=[a for a in accounts if a.is_merchant and a.devices],
  )
  n_scenarios = max(1, round(len(batch.transactions) * fraud_rate / AVG_FRAUD_TX_PER_SCENARIO))
  kinds = rng.choice(FRAUD_TYPES, size=n_scenarios, p=SCENARIO_WEIGHTS)
  span_seconds = (days - 2) * 86_400
  for kind in kinds:
    t = start + timedelta(days=1, seconds=float(rng.uniform(0, span_seconds)))
    batch.extend(SCENARIOS[str(kind)](ctx, t))

  batch.transactions.sort(key=lambda tx: tx.created_at)
  batch.events.sort(key=lambda ev: ev.occurred_at)
  return batch
