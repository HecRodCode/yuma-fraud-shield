from datetime import datetime

import numpy as np

from simulator.domain.models import Customer, SimTransaction, new_id, round_cop

OPERATIONS = [
  "instant_transfer", "qr_payment", "bill_payment", "correspondent_withdrawal",
  "atm_withdrawal", "mobile_topup", "virtual_card_purchase",
]
PROBABILITIES = [0.43, 0.21, 0.10, 0.09, 0.05, 0.08, 0.04]
CHANNELS = {"correspondent_withdrawal": "correspondent", "atm_withdrawal": "atm"}
FIXED_DESTINATIONS = {
  "bill_payment": ("SRV", "utility", 60),
  "mobile_topup": ("OPE", "carrier", 20),
  "correspondent_withdrawal": ("COR", "correspondent", 200),
  "atm_withdrawal": ("CAJ", "atm", 150),
  "virtual_card_purchase": ("COM", "merchant", 500),
}


def pick(rng: np.random.Generator, options: list):
  return options[int(rng.integers(0, len(options)))]


def build_legit(rng: np.random.Generator, customer: Customer, at: datetime) -> SimTransaction:
  operation = str(rng.choice(OPERATIONS, p=PROBABILITIES))
  new_destination = False

  if operation == "instant_transfer":
    if customer.contacts and rng.random() < 0.85:
      destination, dtype = pick(rng, customer.contacts)
    else:
      destination, dtype, new_destination = f"EXT{int(rng.integers(10000, 99999))}", "other_bank", True
  elif operation == "qr_payment":
    if customer.merchants and rng.random() < 0.85:
      destination, dtype = pick(rng, customer.merchants)
    else:
      destination, dtype, new_destination = f"COM{int(rng.integers(10000, 99999))}", "merchant", True
  else:
    prefix, dtype, size = FIXED_DESTINATIONS[operation]
    destination = f"{prefix}{int(rng.integers(1, size)):03d}"

  balance = customer.balance * float(rng.uniform(0.8, 1.2))
  amount = round_cop(min(rng.lognormal(np.log(max(customer.avg_amount, 5000)), 0.5), balance * 0.9))
  return SimTransaction(
    id=new_id(rng, "TS"),
    customer_id=customer.id,
    operation_type=operation,
    channel=CHANNELS.get(operation, "app"),
    amount=amount,
    balance_before=round_cop(max(balance, amount * 1.05)),
    destination_id=destination,
    destination_type=dtype,
    new_destination=new_destination,
    device_id=customer.usual_device,
    new_device=False,
    password_change_24h=False,
    sim_change_48h=False,
    ip_department=customer.usual_ip,
    ip_department_mismatch=False,
    account_age_days=customer.age_days(at),
    occurred_at=at,
  )
