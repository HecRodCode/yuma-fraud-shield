from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from simulator.domain.models import (
  Account,
  Batch,
  SessionEvent,
  Transaction,
  cop,
  new_account_id,
  new_device_id,
  new_uuid,
)


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

  def event(self, account: str, type_: str, device: str, at: datetime) -> SessionEvent:
    return SessionEvent(new_uuid(self.rng), account, type_, device, at)

  def fraud_tx(
    self,
    source: str,
    target: str,
    amount: float,
    channel: str,
    device: str | None,
    at: datetime,
    fraud_type: str,
  ) -> Transaction:
    return Transaction(
      new_uuid(self.rng), source, target, cop(amount), channel, device, at, True, fraud_type
    )
