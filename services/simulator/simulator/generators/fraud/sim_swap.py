from datetime import datetime, timedelta

from simulator.domain.models import Batch, new_device_id
from simulator.generators.fraud.context import Context


def sim_swap(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  if rng.random() < 0.6:
    t = t.replace(hour=int(rng.integers(0, 6)))
  victim = ctx.pick_victim(t)
  mule = ctx.pick_mule(t, batch)
  device = new_device_id(rng) if rng.random() < 0.7 else victim.devices[-1]

  batch.events.append(ctx.event(victim.id, "phone_change", victim.devices[-1], t))
  otp_at = t + timedelta(minutes=float(rng.uniform(1, 10)))
  batch.events.append(ctx.event(victim.id, "otp_requested", device, otp_at))

  at = otp_at
  for _ in range(int(rng.integers(1, 3))):
    at += timedelta(minutes=float(rng.uniform(0.5, 5)))
    amount = victim.avg_amount * rng.uniform(2, 8)
    batch.transactions.append(
      ctx.fraud_tx(victim.id, mule.id, amount, "transfer", device, at, "sim_swap")
    )
  return batch
