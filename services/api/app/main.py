from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import admin, health, scoring
from app.core.settings import KAFKA_BOOTSTRAP
from app.domain.model import Scorer
from app.infra.database import create_pool
from app.infra.kafka import Publisher
from app.services.scoring_service import ScoringService


@asynccontextmanager
async def lifespan(app: FastAPI):
  pool = create_pool()
  publisher = Publisher(KAFKA_BOOTSTRAP)
  app.state.scoring_service = ScoringService(pool, Scorer(), publisher)
  yield
  publisher.flush()
  pool.close()


def create_app() -> FastAPI:
  app = FastAPI(
    title="Yuma Shield scoring API",
    version="0.1.0",
    description=(
      "Real-time fraud scoring for Yuma Pay. Each transaction is scored before "
      "authorization and answered with a decision and plain-language reasons."
    ),
    lifespan=lifespan,
  )

  @app.get("/", include_in_schema=False)
  def root() -> RedirectResponse:
    return RedirectResponse("/docs")

  app.include_router(health.router)
  app.include_router(scoring.router)
  app.include_router(admin.router)
  return app


app = create_app()
