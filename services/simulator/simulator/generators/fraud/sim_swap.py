from datetime import datetime

from simulator.domain.models import Batch, new_device
from simulator.generators.fraud.context import Context, minutes


def sim_swap(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  victim = ctx.victim()
  device = new_device(rng)
  department = victim.usual_ip

  batch.events.append(ctx.event(victim, "sim_change", victim.usual_device, t))
  registration = t + minutes(4)
  batch.events.append(ctx.event(victim, "device_registration", device, registration))
  batch.events.append(ctx.event(victim, "login", device, registration + minutes(1)))

  amount = victim.balance * rng.uniform(0.6, 0.95)
  destination, dtype = ctx.external_destination()
  at = registration + minutes(3)
  batch.transactions.append(
    ctx.fraud_tx(
      victim, at, "sim_swap", amount, destination, dtype, device=device, new_device=True,
      sim_change=True, department=department,
    )
  )
  remaining = victim.balance - amount
  if remaining > 100_000 and rng.random() < 0.5:
    batch.transactions.append(
      ctx.fraud_tx(
        victim, at + minutes(rng.uniform(10, 25)), "sim_swap", remaining * 0.95, "CAJ031", "atm",
        operation="atm_withdrawal", channel="atm", balance=remaining, device=device,
        new_device=True, sim_change=True, department=department,
      )
    )
  return batch
