from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_scoring_service
from app.domain.model import ModelNotReadyError
from app.schemas.scoring import ScoreRequest, ScoreResponse
from app.services.scoring_service import ScoringService

router = APIRouter(tags=["scoring"])


@router.post(
  "/score",
  response_model=ScoreResponse,
  summary="Score a transaction before authorizing it",
  responses={503: {"description": "Model not trained yet (run make train)"}},
)
def score(
  req: ScoreRequest, service: ScoringService = Depends(get_scoring_service)
) -> ScoreResponse:
  """Applies hard rules, behavior and device features, and the XGBoost model.

  Returns the decision (approve, challenge or hold), the risk score and the main
  reasons in plain language. The decision is also published to Kafka for persistence.
  """
  try:
    return service.score(req)
  except ModelNotReadyError as error:
    raise HTTPException(status_code=503, detail=str(error))
