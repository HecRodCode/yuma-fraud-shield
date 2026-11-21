from fastapi import APIRouter, Depends

from app.api.deps import get_scoring_service
from app.services.scoring_service import ScoringService

router = APIRouter(tags=["health"])


@router.get("/health")
def health(service: ScoringService = Depends(get_scoring_service)) -> dict:
  return {
    "status": "ok",
    "model_loaded": service.scorer.ready,
    "model_version": service.scorer.version,
  }
