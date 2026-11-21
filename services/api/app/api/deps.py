from fastapi import Request

from app.services.scoring_service import ScoringService


def get_scoring_service(request: Request) -> ScoringService:
  return request.app.state.scoring_service
