import httpx

from simulator.domain.models import SimTransaction
from simulator.settings import API_URL


def create_client() -> httpx.Client:
  return httpx.Client(base_url=API_URL, timeout=10)


def score_payload(tx: SimTransaction) -> dict:
  return {
    "transaction_id": tx.id,
    "occurred_at": tx.occurred_at.isoformat(),
    "customer_id": tx.customer_id,
    "operation_type": tx.operation_type,
    "channel": tx.channel,
    "amount": tx.amount,
    "balance_before": tx.balance_before,
    "destination_id": tx.destination_id,
    "destination_type": tx.destination_type,
    "new_destination": tx.new_destination,
    "device_id": tx.device_id,
    "new_device": tx.new_device,
    "password_change_24h": tx.password_change_24h,
    "sim_change_48h": tx.sim_change_48h,
    "ip_department": tx.ip_department,
    "ip_department_mismatch": tx.ip_department_mismatch,
    "account_age_days": tx.account_age_days,
    "meta": {"is_fraud": tx.is_fraud, "fraud_type": tx.fraud_type, "source": "simulated"},
  }
