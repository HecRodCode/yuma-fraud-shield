from datetime import datetime

from simulator.domain.models import Batch
from simulator.generators.fraud.context import Context, minutes


def mule_account(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  mule = ctx.mule()
  victims: set[str] = set()
  total = 0.0

  for offset in sorted(float(x) for x in rng.uniform(0, 60, int(rng.integers(6, 15)))):
    victim = ctx.victim(exclude=victims | {mule.id})
    victims.add(victim.id)
    amount = victim.balance * rng.uniform(0.3, 0.9)
    total += amount
    batch.transactions.append(
      ctx.fraud_tx(
        victim, t + minutes(offset), "social_engineering", amount, mule.id, "yuma_account"
      )
    )

  cash_out = t + minutes(rng.uniform(65, 90))
  withdrawal = rng.choice(["correspondent_withdrawal", "atm_withdrawal"])
  channel = "correspondent" if withdrawal == "correspondent_withdrawal" else "atm"
  batch.transactions.append(
    ctx.fraud_tx(
      mule, cash_out, "mule_account", total * 0.95, "COR044" if channel == "correspondent" else "CAJ044",
      channel, operation=str(withdrawal), channel=channel, balance=total,
    )
  )
  return batch
