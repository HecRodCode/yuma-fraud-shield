from datetime import datetime, timedelta

import numpy as np

from simulator.domain.models import SYSTEM_ACCOUNT, Account, new_account_id, new_device_id


def build_population(
  rng: np.random.Generator, n_accounts: int, start: datetime, end: datetime
) -> list[Account]:
  span_days = (end - start).days
  accounts = [
    Account(
      id=SYSTEM_ACCOUNT,
      created_at=start - timedelta(days=3650),
      is_merchant=True,
    )
  ]

  for _ in range(n_accounts):
    is_merchant = rng.random() < 0.08
    if rng.random() < 0.08:
      created_at = start + timedelta(days=float(rng.uniform(0, span_days * 0.9)))
    else:
      created_at = start - timedelta(days=float(rng.uniform(30, 900)))

    devices = [new_device_id(rng)]
    if rng.random() < 0.15:
      devices.append(new_device_id(rng))

    rate = float(np.clip(rng.gamma(2.0, 0.35), 0.05, 3.0))
    accounts.append(
      Account(
        id=new_account_id(rng),
        created_at=created_at,
        is_merchant=is_merchant,
        devices=devices,
        avg_amount=float(rng.lognormal(np.log(70_000), 0.7)),
        daily_rate=rate * 0.2 if is_merchant else rate,
        active_start=int(rng.integers(6, 15)),
        active_len=int(rng.integers(10, 15)),
      )
    )

  regular = [a for a in accounts[1:] if not a.is_merchant]
  merchants = [a for a in accounts[1:] if a.is_merchant]
  for acc in accounts[1:]:
    peers = rng.choice(len(regular), size=int(rng.integers(4, 13)), replace=False)
    acc.contacts = [regular[i].id for i in peers if regular[i].id != acc.id]
    shops = rng.choice(len(merchants), size=min(len(merchants), int(rng.integers(2, 5))), replace=False)
    acc.favorite_merchants = [merchants[i].id for i in shops if merchants[i].id != acc.id]

  return accounts
