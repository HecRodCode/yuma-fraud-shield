from datetime import datetime, timedelta

from simulator.domain.models import SYSTEM_ACCOUNT, Batch, cop
from simulator.generators.fraud.context import Context


def mule_account(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  mule = ctx.new_mule(t, batch)
  device = mule.devices[0]
  batch.events.append(ctx.event(mule.id, "login", device, t - timedelta(minutes=5)))

  n_sources = int(rng.integers(8, 26))
  offsets = sorted(float(x) for x in rng.uniform(0, 90, n_sources))
  total = 0.0
  for offset in offsets:
    victim = ctx.pick_victim(t)
    amount = victim.avg_amount * rng.uniform(0.5, 2)
    total += cop(amount)
    batch.transactions.append(
      ctx.fraud_tx(
        victim.id,
        mule.id,
        amount,
        "transfer",
        victim.devices[-1],
        t + timedelta(minutes=offset),
        "mule_account",
      )
    )

  cash_out = t + timedelta(minutes=offsets[-1] + float(rng.uniform(2, 20)))
  batch.transactions.append(
    ctx.fraud_tx(
      mule.id, SYSTEM_ACCOUNT, total * 0.9, "withdrawal", device, cash_out, "mule_account"
    )
  )
  return batch
