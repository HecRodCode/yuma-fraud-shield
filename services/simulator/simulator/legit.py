from datetime import datetime, timedelta

import numpy as np

from .models import (
  SYSTEM_ACCOUNT,
  Account,
  Batch,
  SessionEvent,
  Transaction,
  cop,
  new_device_id,
  new_uuid,
)

CHANNELS = ["transfer", "qr", "bill_payment", "topup", "withdrawal"]
CHANNEL_PROBS = [0.35, 0.30, 0.10, 0.10, 0.15]
PAYDAYS = (1, 15, 30)


def generate_legit(
  rng: np.random.Generator, accounts: list[Account], start: datetime, end: datetime
) -> Batch:
  batch = Batch()
  by_id = {a.id: a for a in accounts}
  regular = [a for a in accounts if a.devices and not a.is_merchant]
  days = (end - start).days

  for acc in accounts:
    if not acc.devices:
      continue
    first_day = max(0, (acc.created_at - start).days + 1)
    for d in range(first_day, days):
      day = start + timedelta(days=d)
      factor = 1.6 if day.day in PAYDAYS else 1.0
      n_tx = int(rng.poisson(acc.daily_rate * factor))
      if n_tx == 0 and rng.random() > 0.3:
        continue

      _maybe_account_changes(rng, acc, day, batch)
      device = acc.devices[-1] if rng.random() < 0.85 else acc.devices[0]
      times = sorted(_active_time(rng, acc, day) for _ in range(max(n_tx, 1)))
      login_at = times[0] - timedelta(minutes=float(rng.uniform(1, 20)))
      batch.events.append(
        SessionEvent(new_uuid(rng), acc.id, "login", device, login_at)
      )

      for t in times[:n_tx]:
        tx = _legit_transaction(rng, acc, by_id, regular, device, t)
        if tx is None:
          continue
        batch.transactions.append(tx)
        if tx.channel == "transfer" and rng.random() < 0.4:
          batch.events.append(
            SessionEvent(
              new_uuid(rng),
              acc.id,
              "otp_requested",
              device,
              t - timedelta(seconds=float(rng.uniform(30, 120))),
            )
          )

  return batch


def _active_time(rng: np.random.Generator, acc: Account, day: datetime) -> datetime:
  hour = (acc.active_start + int(rng.integers(0, acc.active_len))) % 24
  return day.replace(
    hour=hour, minute=int(rng.integers(0, 60)), second=int(rng.integers(0, 60))
  )


def _maybe_account_changes(
  rng: np.random.Generator, acc: Account, day: datetime, batch: Batch
) -> None:
  at = _active_time(rng, acc, day)
  if rng.random() < 0.002:
    device = new_device_id(rng)
    acc.devices.append(device)
    batch.events.append(SessionEvent(new_uuid(rng), acc.id, "device_change", device, at))
  if rng.random() < 0.0015:
    batch.events.append(
      SessionEvent(new_uuid(rng), acc.id, "password_change", acc.devices[-1], at)
    )
  if rng.random() < 0.0003:
    batch.events.append(
      SessionEvent(new_uuid(rng), acc.id, "phone_change", acc.devices[-1], at)
    )


def _legit_transaction(
  rng: np.random.Generator,
  acc: Account,
  by_id: dict[str, Account],
  regular: list[Account],
  device: str,
  t: datetime,
) -> Transaction | None:
  channel = str(rng.choice(CHANNELS, p=CHANNEL_PROBS))

  if channel == "transfer":
    pool = acc.contacts
    if rng.random() < 0.1:
      target = regular[int(rng.integers(0, len(regular)))].id
    elif pool:
      target = pool[int(rng.integers(0, len(pool)))]
    else:
      return None
  elif channel in ("qr", "bill_payment"):
    if not acc.favorite_merchants:
      return None
    pool = acc.favorite_merchants
    target = pool[int(rng.integers(0, len(pool)))]
  else:
    target = SYSTEM_ACCOUNT

  if target == acc.id or by_id[target].created_at > t:
    return None

  amount = rng.lognormal(np.log(acc.avg_amount), 0.6)
  if rng.random() < 0.015:
    amount *= rng.uniform(4, 10)

  return Transaction(
    id=new_uuid(rng),
    source_account=acc.id,
    target_account=target,
    amount=cop(amount),
    channel=channel,
    device=device,
    created_at=t,
  )
