from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from simulator.control.jobs import Job, JobRunner
from simulator.generators.fraud import FRAUD_TYPES

app = FastAPI(
  title="Yuma Shield simulator control",
  version="0.2.0",
  description="Launches live traffic, attacks and sandbox runs as background jobs.",
)
runner = JobRunner()


class LiveParams(BaseModel):
  tps: float = Field(5, gt=0, le=200)
  duration: float = Field(30, gt=0, le=600)


class AttackParams(BaseModel):
  type: Literal[tuple(FRAUD_TYPES)]
  speedup: float = Field(60, gt=0, le=3600, description="Virtual seconds per real second.")


class SandboxParams(BaseModel):
  start: str = Field("2026-10-01 00:00:00", description="Decide transactions from this local time.")
  reset: bool = True
  limit: int | None = Field(None, gt=0)


def _view(job: Job, tail: int = 30) -> dict:
  return {
    "id": job.id, "type": job.type, "params": job.params, "status": job.status,
    "started_at": job.started_at, "ended_at": job.ended_at, "log": job.log[-tail:],
  }


@app.get("/health")
def health() -> dict:
  return {"status": "ok", "running": runner.running()}


@app.post("/jobs/live", summary="Send legitimate traffic to the scoring API")
def live(params: LiveParams) -> dict:
  steps = [["live", "--tps", str(params.tps), "--duration", str(params.duration)]]
  return _view(runner.start("live", params.model_dump(), steps))


@app.post("/jobs/attack", summary="Launch one fraud scenario")
def attack(params: AttackParams) -> dict:
  steps = [["attack", params.type, "--speedup", str(params.speedup)]]
  return _view(runner.start("attack", params.model_dump(), steps))


@app.post("/jobs/sandbox", summary="Decide the test period through the case sandbox")
def sandbox(params: SandboxParams) -> dict:
  if runner.running("sandbox"):
    raise HTTPException(409, "a sandbox job is already running")
  step = ["sandbox", "--start", params.start]
  if params.reset:
    step.append("--reset")
  if params.limit:
    step += ["--limit", str(params.limit)]
  return _view(runner.start("sandbox", params.model_dump(), [step]))


@app.get("/jobs", summary="List jobs, most recent first")
def list_jobs() -> list[dict]:
  jobs = sorted(runner.jobs.values(), key=lambda j: j.started_at, reverse=True)
  return [_view(j, tail=5) for j in jobs]


@app.get("/jobs/{job_id}", summary="Job status and log")
def get_job(job_id: str) -> dict:
  job = runner.jobs.get(job_id)
  if job is None:
    raise HTTPException(404, "job not found")
  return _view(job, tail=200)
