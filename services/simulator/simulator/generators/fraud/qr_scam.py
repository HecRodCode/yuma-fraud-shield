from datetime import datetime

import numpy as np

from simulator.domain.models import Batch, new_id
from simulator.generators.fraud.context import Context, minutes


def qr_scam(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  merchant = f"COM{int(rng.integers(80000, 99999))}"
  victims: set[str] = set()
  for offset in sorted(float(x) for x in rng.uniform(0, 40, int(rng.integers(8, 21)))):
    victim = ctx.victim(exclude=victims)
    victims.add(victim.id)
    amount = min(rng.lognormal(np.log(max(victim.avg_amount, 20_000)), 0.4), victim.balance * 0.8)
    batch.transactions.append(
      ctx.fraud_tx(
        victim, t + minutes(offset), "qr_scam", amount, merchant, "merchant",
        operation="qr_payment",
      )
    )
  return batch
