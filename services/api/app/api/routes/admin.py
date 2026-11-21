from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_scoring_service
from app.domain.model import ModelNotReadyError
from app.services.scoring_service import ScoringService
from app.workers.replay import run_replay

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/replay", summary="Score stored transactions that have no decision yet")
def replay(
  all: bool = False, service: ScoringService = Depends(get_scoring_service)
) -> dict:
  """Scores stored transactions in bulk so both engines can be compared.

  By default only the held-out part of the history (not used for training) is scored.
  With `all=true` every transaction without a decision is scored; use it after generating
  a new seed, whose data the model has never seen.
  """
  try:
    return run_replay(service.scorer, replay_all=all)
  except ModelNotReadyError as error:
    raise HTTPException(status_code=503, detail=str(error))
