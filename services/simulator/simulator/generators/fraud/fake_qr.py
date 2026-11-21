from datetime import datetime, timedelta

import numpy as np

from simulator.domain.models import Account, Batch, new_account_id
from simulator.generators.fraud.context import Context


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
      ctx.fraud_tx(
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
