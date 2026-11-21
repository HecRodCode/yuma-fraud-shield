from datetime import datetime

from simulator.domain.models import Batch
from simulator.generators.fraud.context import Context


def social_engineering(ctx: Context, t: datetime) -> Batch:
  batch = Batch()
  victim = ctx.victim()
  destination, dtype = ctx.external_destination()
  amount = victim.balance * ctx.rng.uniform(0.7, 0.98)
  batch.transactions.append(
    ctx.fraud_tx(victim, t, "social_engineering", amount, destination, dtype)
  )
  return batch
