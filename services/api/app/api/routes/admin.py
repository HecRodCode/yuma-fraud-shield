from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_scoring_service
from app.domain.model import ModelNotReadyError
from app.services.scoring_service import ScoringService
from app.services import retrain_service
from app.services.retrain_service import RetrainRunningError
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


@router.post("/retrain", summary="Retrain the model, optionally using analyst feedback")
def retrain(use_feedback: bool = True) -> dict:
  """Starts a training run in the background and publishes the new model when it ends.

  With `use_feedback=true`, analyst verdicts and customer claims become training labels
  (operations after the dataset period, plus labels before the October test month).
  The API picks up the new model and thresholds automatically.
  """
  try:
    return retrain_service.start(use_feedback)
  except RetrainRunningError as error:
    raise HTTPException(status_code=409, detail=str(error))


@router.get("/retrain", summary="Status and log of the latest training run")
def retrain_status() -> dict:
  return retrain_service.status()


@router.post("/models/{version}/promote", summary="Publish a stored model version (rollback)")
def promote_model(version: str) -> dict:
  from shield_ml.registry import promote, version_dir

  if not version_dir(version).exists():
    raise HTTPException(status_code=404, detail="unknown model version")
  promote(version, actor="api")
  return {"active": version}
