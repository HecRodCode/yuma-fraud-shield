from datetime import datetime

from simulator.domain.models import Batch, new_device
from simulator.generators.fraud.context import Context, minutes


def account_takeover(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  victim = ctx.victim()
  device = new_device(rng)
  department = ctx.other_department(victim)

  for i in range(int(rng.integers(1, 4))):
    batch.events.append(
      ctx.event(victim, "login", device, t + minutes(i * 0.7), "failed", department)
    )
  registration = t + minutes(3)
  batch.events.append(ctx.event(victim, "device_registration", device, registration, "success", department))
  batch.events.append(ctx.event(victim, "login", device, registration + minutes(0.5), "success", department))
  password = registration + minutes(2)
  batch.events.append(ctx.event(victim, "password_change", device, password, "success", department))

  balance = victim.balance
  at = password
  for _ in range(int(rng.integers(2, 5))):
    at += minutes(rng.uniform(2, 15))
    amount = min(balance, victim.balance * rng.uniform(0.2, 0.45))
    destination, dtype = ctx.external_destination()
    batch.transactions.append(
      ctx.fraud_tx(
        victim, at, "account_takeover", amount, destination, dtype, balance=balance,
        device=device, new_device=True, password_change=True, department=department,
      )
    )
    balance -= amount
  return batch
