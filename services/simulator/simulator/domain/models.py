import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np


@dataclass
class Customer:
  id: str
  joined_on: date
  is_mule: bool
  usual_device: str | None = None
  usual_ip: str | None = None
  avg_amount: float = 50_000.0
  balance: float = 500_000.0
  n_tx: int = 0
  contacts: list[tuple[str, str]] = field(default_factory=list)
  merchants: list[tuple[str, str]] = field(default_factory=list)

  def age_days(self, at: datetime) -> int:
    return max(0, (at.date() - self.joined_on).days)


@dataclass
class SessionEvent:
  id: str
  customer_id: str
  type: str
  device_id: str | None
  os: str
  ip_department: str | None
  result: str
  occurred_at: datetime


@dataclass
class SimTransaction:
  id: str
  customer_id: str
  operation_type: str
  channel: str
  amount: float
  balance_before: float
  destination_id: str
  destination_type: str
  new_destination: bool
  device_id: str | None
  new_device: bool
  password_change_24h: bool
  sim_change_48h: bool
  ip_department: str | None
  ip_department_mismatch: bool
  account_age_days: int
  occurred_at: datetime
  is_fraud: bool = False
  fraud_type: str | None = None


@dataclass
class Batch:
  events: list[SessionEvent] = field(default_factory=list)
  transactions: list[SimTransaction] = field(default_factory=list)


def new_id(rng: np.random.Generator, prefix: str) -> str:
  return f"{prefix}-{rng.bytes(5).hex()}"


def new_device(rng: np.random.Generator) -> str:
  return "DSIM" + rng.bytes(4).hex().upper()


def round_cop(value: float) -> float:
  return max(1000.0, round(float(value) / 100) * 100)
