from datetime import datetime, timedelta

from simulator.domain.models import Batch, new_device_id
from simulator.generators.fraud.context import Context


def account_takeover(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  victim = ctx.pick_victim(t)
  mule = ctx.pick_mule(t, batch)
  device = new_device_id(rng)

  batch.events.append(ctx.event(victim.id, "device_change", device, t))
  batch.events.append(ctx.event(victim.id, "login", device, t + timedelta(seconds=20)))
  pwd_at = t + timedelta(minutes=float(rng.uniform(1, 30)))
  batch.events.append(ctx.event(victim.id, "password_change", device, pwd_at))

  at = pwd_at
  for _ in range(int(rng.integers(1, 4))):
    at += timedelta(minutes=float(rng.uniform(2, 60)))
    amount = victim.avg_amount * rng.uniform(3, 10)
    batch.transactions.append(
      ctx.fraud_tx(victim.id, mule.id, amount, "transfer", device, at, "account_takeover")
    )
  return batch
