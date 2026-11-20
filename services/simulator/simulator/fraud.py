from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .models import (
  SYSTEM_ACCOUNT,
  Account,
  Batch,
  SessionEvent,
  Transaction,
  cop,
  new_account_id,
  new_device_id,
  new_uuid,
)

FRAUD_TYPES = ["account_takeover", "sim_swap", "mule_account", "fake_qr"]
SCENARIO_WEIGHTS = [0.40, 0.35, 0.15, 0.10]
AVG_FRAUD_TX_PER_SCENARIO = 7.8


@dataclass
class Context:
  rng: np.random.Generator
  victims: list[Account]
  merchants: list[Account]
  mule_pool: list[Account] = field(default_factory=list)

  def pick_victim(self, t: datetime) -> Account:
    while True:
      acc = self.victims[int(self.rng.integers(0, len(self.victims)))]
      if acc.created_at < t - timedelta(days=1):
        return acc

  def pick_mule(self, t: datetime, batch: Batch) -> Account:
    usable = [m for m in self.mule_pool if m.created_at <= t]
    if usable and self.rng.random() < 0.6:
      return usable[int(self.rng.integers(0, len(usable)))]
    return self.new_mule(t, batch)

  def new_mule(self, t: datetime, batch: Batch) -> Account:
    mule = Account(
      id=new_account_id(self.rng),
      created_at=t - timedelta(hours=float(self.rng.uniform(2, 72))),
      is_merchant=False,
      devices=[new_device_id(self.rng)],
      avg_amount=50_000,
    )
    self.mule_pool.append(mule)
    batch.accounts.append(mule)
    return mule


def _event(ctx: Context, account: str, type_: str, device: str, at: datetime) -> SessionEvent:
  return SessionEvent(new_uuid(ctx.rng), account, type_, device, at)


def _tx(
  ctx: Context,
  source: str,
  target: str,
  amount: float,
  channel: str,
  device: str | None,
  at: datetime,
  fraud_type: str,
) -> Transaction:
  return Transaction(
    new_uuid(ctx.rng), source, target, cop(amount), channel, device, at, True, fraud_type
  )


def account_takeover(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  victim = ctx.pick_victim(t)
  mule = ctx.pick_mule(t, batch)
  device = new_device_id(rng)

  batch.events.append(_event(ctx, victim.id, "device_change", device, t))
  batch.events.append(_event(ctx, victim.id, "login", device, t + timedelta(seconds=20)))
  pwd_at = t + timedelta(minutes=float(rng.uniform(1, 30)))
  batch.events.append(_event(ctx, victim.id, "password_change", device, pwd_at))

  at = pwd_at
  for _ in range(int(rng.integers(1, 4))):
    at += timedelta(minutes=float(rng.uniform(2, 60)))
    amount = victim.avg_amount * rng.uniform(3, 10)
    batch.transactions.append(
      _tx(ctx, victim.id, mule.id, amount, "transfer", device, at, "account_takeover")
    )
  return batch


def sim_swap(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  if rng.random() < 0.6:
    t = t.replace(hour=int(rng.integers(0, 6)))
  victim = ctx.pick_victim(t)
  mule = ctx.pick_mule(t, batch)
  device = new_device_id(rng) if rng.random() < 0.7 else victim.devices[-1]

  batch.events.append(_event(ctx, victim.id, "phone_change", victim.devices[-1], t))
  otp_at = t + timedelta(minutes=float(rng.uniform(1, 10)))
  batch.events.append(_event(ctx, victim.id, "otp_requested", device, otp_at))

  at = otp_at
  for _ in range(int(rng.integers(1, 3))):
    at += timedelta(minutes=float(rng.uniform(0.5, 5)))
    amount = victim.avg_amount * rng.uniform(2, 8)
    batch.transactions.append(
      _tx(ctx, victim.id, mule.id, amount, "transfer", device, at, "sim_swap")
    )
  return batch


def mule_account(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  mule = ctx.new_mule(t, batch)
  device = mule.devices[0]
  batch.events.append(_event(ctx, mule.id, "login", device, t - timedelta(minutes=5)))

  n_sources = int(rng.integers(8, 26))
  offsets = sorted(float(x) for x in rng.uniform(0, 90, n_sources))
  total = 0.0
  for offset in offsets:
    victim = ctx.pick_victim(t)
    amount = victim.avg_amount * rng.uniform(0.5, 2)
    total += cop(amount)
    batch.transactions.append(
      _tx(
        ctx,
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
    _tx(ctx, mule.id, SYSTEM_ACCOUNT, total * 0.9, "withdrawal", device, cash_out, "mule_account")
  )
  return batch


def fake_qr(ctx: Context, t: datetime) -> Batch:
  rng = ctx.rng
  batch = Batch()
  if rng.random() < 0.5:
    merchant = ctx.merchants[int(rng.integers(0, len(ctx.merchants)))]
  else:
    merchant = Account(
      id=new_account_id(rng),
      created_at=t - timedelta(days=float(rng.uniform(1, 10))),
      is_merchant=True,
    )
    batch.accounts.append(merchant)

  n_payments = int(rng.integers(15, 61))
  for offset in sorted(float(x) for x in rng.uniform(0, 70, n_payments)):
    payer = ctx.pick_victim(t)
    amount = rng.lognormal(np.log(15_000), 0.3)
    batch.transactions.append(
      _tx(
        ctx,
        payer.id,
        merchant.id,
        amount,
        "qr",
        payer.devices[-1],
        t + timedelta(minutes=offset),
        "fake_qr",
      )
    )
  return batch


SCENARIOS = {
  "account_takeover": account_takeover,
  "sim_swap": sim_swap,
  "mule_account": mule_account,
  "fake_qr": fake_qr,
}
