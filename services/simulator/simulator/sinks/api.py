import httpx

from simulator.domain.models import Transaction
from simulator.settings import API_URL


def create_client() -> httpx.Client:
  return httpx.Client(base_url=API_URL, timeout=5)


def score_payload(tx: Transaction) -> dict:
  return {
    "transaction_id": str(tx.id),
    "source_account": tx.source_account,
    "target_account": tx.target_account,
    "amount": tx.amount,
    "channel": tx.channel,
    "device": tx.device,
    "meta": {"is_fraud": tx.is_fraud, "fraud_type": tx.fraud_type},
  }
