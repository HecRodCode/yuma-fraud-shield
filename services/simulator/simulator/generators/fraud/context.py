from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from simulator.domain.models import (
  Customer,
  SessionEvent,
  SimTransaction,
  new_id,
  round_cop,
)


@dataclass
class Context:
  rng: np.random.Generator
  customers: list[Customer]
  departments: list[str]

  def victim(self, exclude: set[str] | None = None) -> Customer:
    pool = [c for c in self.customers if not c.is_mule and c.balance > 100_000]
    while True:
      candidate = pool[int(self.rng.integers(0, len(pool)))]
      if not exclude or candidate.id not in exclude:
        return candidate

  def mule(self) -> Customer:
    mules = sorted((c for c in self.customers if c.is_mule), key=lambda c: c.joined_on, reverse=True)
    mules = mules[:15]
    return mules[int(self.rng.integers(0, len(mules)))]

  def other_department(self, customer: Customer) -> str:
    choices = [d for d in self.departments if d != customer.usual_ip]
    return choices[int(self.rng.integers(0, len(choices)))]

  def event(
    self, customer: Customer, type_: str, device: str | None, at: datetime,
    result: str = "success", department: str | None = None,
  ) -> SessionEvent:
    return SessionEvent(
      id=new_id(self.rng, "ES"),
      customer_id=customer.id,
      type=type_,
      device_id=device,
      os="Android",
      ip_department=department or customer.usual_ip,
      result=result,
      occurred_at=at,
    )

  def fraud_tx(
    self,
    customer: Customer,
    at: datetime,
    fraud_type: str,
    amount: float,
    destination_id: str,
    destination_type: str,
    operation: str = "instant_transfer",
    channel: str = "app",
    balance: float | None = None,
    device: str | None = None,
    new_device: bool = False,
    password_change: bool = False,
    sim_change: bool = False,
    department: str | None = None,
  ) -> SimTransaction:
    balance = balance if balance is not None else customer.balance
    department = department or customer.usual_ip
    return SimTransaction(
      id=new_id(self.rng, "TF"),
      customer_id=customer.id,
      operation_type=operation,
      channel=channel,
      amount=round_cop(amount),
      balance_before=round_cop(max(balance, amount)),
      destination_id=destination_id,
      destination_type=destination_type,
      new_destination=True,
      device_id=device or customer.usual_device,
      new_device=new_device,
      password_change_24h=password_change,
      sim_change_48h=sim_change,
      ip_department=department,
      ip_department_mismatch=department != customer.usual_ip,
      account_age_days=customer.age_days(at),
      occurred_at=at,
      is_fraud=True,
      fraud_type=fraud_type,
    )

  def external_destination(self) -> tuple[str, str]:
    return f"EXT{int(self.rng.integers(10000, 99999))}", "other_bank"


def minutes(value: float) -> timedelta:
  return timedelta(minutes=float(value))
