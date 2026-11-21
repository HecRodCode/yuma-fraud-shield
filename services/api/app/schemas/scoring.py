import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
  transaction_id: uuid.UUID | None = None
  source_account: str
  target_account: str
  amount: float = Field(gt=0)
  channel: Literal["transfer", "qr", "bill_payment", "topup", "withdrawal"]
  device: str | None = None
  created_at: datetime | None = None
  meta: dict | None = None


class Reason(BaseModel):
  feature: str
  text: str
  effect: str
  impact: float


class ScoreResponse(BaseModel):
  decision_id: uuid.UUID
  transaction_id: uuid.UUID
  action: Literal["approve", "challenge", "hold"]
  score: float
  reasons: list[Reason]
  latency_ms: float
  model_version: str
