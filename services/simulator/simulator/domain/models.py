from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import numpy as np

SYSTEM_ACCOUNT = "sys_cashpoint"


@dataclass(slots=True)
class Account:
  id: str
  created_at: datetime
  is_merchant: bool
  devices: list[str] = field(default_factory=list)
  avg_amount: float = 0.0
  daily_rate: float = 0.0
  active_start: int = 8
  active_len: int = 12
  contacts: list[str] = field(default_factory=list)
  favorite_merchants: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionEvent:
  id: UUID
  account_id: str
  type: str
  device: str | None
  occurred_at: datetime


@dataclass(slots=True)
class Transaction:
  id: UUID
  source_account: str
  target_account: str
  amount: float
  channel: str
  device: str | None
  created_at: datetime
  is_fraud: bool = False
  fraud_type: str | None = None


@dataclass
class Batch:
  accounts: list[Account] = field(default_factory=list)
  events: list[SessionEvent] = field(default_factory=list)
  transactions: list[Transaction] = field(default_factory=list)

  def extend(self, other: "Batch") -> None:
    self.accounts += other.accounts
    self.events += other.events
    self.transactions += other.transactions


def new_uuid(rng: np.random.Generator) -> UUID:
  return UUID(bytes=rng.bytes(16), version=4)


def new_account_id(rng: np.random.Generator) -> str:
  return "acc_" + rng.bytes(6).hex()


def new_device_id(rng: np.random.Generator) -> str:
  return "dev_" + rng.bytes(5).hex()


def cop(value: float) -> float:
  return max(1000.0, round(float(value) / 100) * 100)
