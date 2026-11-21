import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OperationType = Literal[
  "instant_transfer", "qr_payment", "bill_payment", "correspondent_withdrawal",
  "atm_withdrawal", "mobile_topup", "virtual_card_purchase",
]
DestinationType = Literal[
  "yuma_account", "other_bank", "merchant", "correspondent", "atm", "utility", "carrier"
]


class ScoreRequest(BaseModel):
  model_config = ConfigDict(
    json_schema_extra={
      "example": {
        "transaction_id": "T-demo-0001",
        "customer_id": "C00001",
        "operation_type": "instant_transfer",
        "channel": "app",
        "amount": 850000,
        "balance_before": 900000,
        "destination_id": "EXT90001",
        "destination_type": "other_bank",
        "new_destination": True,
        "device_id": "D0000001",
        "new_device": True,
        "password_change_24h": True,
        "sim_change_48h": False,
        "ip_department": "Antioquia",
        "ip_department_mismatch": False,
        "account_age_days": 400,
      }
    }
  )

  transaction_id: str | None = Field(None, description="Optional id; generated when omitted.")
  occurred_at: datetime | None = Field(None, description="Defaults to the time of the request.")
  customer_id: str = Field(description="Customer that originates the operation.")
  operation_type: OperationType
  channel: Literal["app", "correspondent", "atm"]
  amount: float = Field(gt=0, description="Amount in COP.")
  balance_before: float = Field(description="Available balance before the operation, in COP.")
  destination_id: str
  destination_type: DestinationType
  new_destination: bool = Field(description="First operation to this destination in 180 days.")
  device_id: str | None = None
  new_device: bool = Field(description="Device registered in the last 24 hours.")
  password_change_24h: bool
  sim_change_48h: bool
  ip_department: str | None = None
  ip_department_mismatch: bool = Field(description="IP area differs from the customer's usual area.")
  account_age_days: int = Field(ge=0)
  meta: dict | None = Field(None, description="Simulation metadata (ground truth); ignored by scoring.")


class Reason(BaseModel):
  feature: str = Field(description="Model feature behind this reason.")
  text: str = Field(description="Plain-language explanation.")
  effect: str = Field(description="raises_risk or lowers_risk.")
  impact: float = Field(description="SHAP contribution to the score (log-odds).")


class ScoreResponse(BaseModel):
  decision_id: uuid.UUID
  transaction_id: str
  action: Literal["approve", "challenge", "hold", "reject"] = Field(
    description=(
      "approve: no friction; challenge: ask for stronger authentication; "
      "hold: retain and alert an analyst; reject: deny the operation."
    )
  )
  score: float = Field(description="Fraud probability between 0 and 1.")
  reasons: list[Reason]
  latency_ms: float
  model_version: str
