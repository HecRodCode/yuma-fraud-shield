from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from simulator.control.jobs import Job, JobRunner
from simulator.generators.fraud import FRAUD_TYPES

app = FastAPI(
  title="Yuma Shield simulator control",
  version="0.1.0",
  description="Launches seeds, live traffic and attacks as background jobs.",
)
runner = JobRunner()


class SeedParams(BaseModel):
  accounts: int = Field(1500, ge=100, le=20000)
  days: int = Field(20, ge=5, le=120)
  fraud_rate: float = Field(0.01, gt=0, le=0.2)
  seed: int = 7
  evaluate: bool = Field(True, description="Score the new data with Yuma Shield afterwards.")


class LiveParams(BaseModel):
  tps: float = Field(5, gt=0, le=200)
  duration: float = Field(30, gt=0, le=600)


class AttackParams(BaseModel):
  type: Literal[tuple(FRAUD_TYPES)]
  speedup: float = Field(20, gt=0, le=600)


def _view(job: Job, tail: int = 30) -> dict:
  return {
    "id": job.id,
    "type": job.type,
    "params": job.params,
    "status": job.status,
    "started_at": job.started_at,
    "ended_at": job.ended_at,
    "log": job.log[-tail:],
  }


@app.get("/health")
def health() -> dict:
  return {"status": "ok", "running": runner.running()}


@app.post("/jobs/seed", summary="Generate a new labeled dataset and compare both engines")
def seed(params: SeedParams) -> dict:
  if runner.running("seed"):
    raise HTTPException(409, "a seed job is already running")
  steps = [
    [
      "history", "--reset", "--accounts", str(params.accounts), "--days", str(params.days),
      "--fraud-rate", str(params.fraud_rate), "--seed", str(params.seed),
    ]
  ]
  if params.evaluate:
    steps.append(["evaluate", "--all"])
  return _view(runner.start("seed", params.model_dump(), steps))


@app.post("/jobs/live", summary="Send legitimate traffic to the scoring API")
def live(params: LiveParams) -> dict:
  steps = [["live", "--tps", str(params.tps), "--duration", str(params.duration)]]
  return _view(runner.start("live", params.model_dump(), steps))


@app.post("/jobs/attack", summary="Launch one fraud scenario")
def attack(params: AttackParams) -> dict:
  steps = [["attack", params.type, "--speedup", str(params.speedup)]]
  return _view(runner.start("attack", params.model_dump(), steps))


@app.post("/jobs/evaluate", summary="Score stored transactions that have no decision yet")
def evaluate(all: bool = False) -> dict:
  steps = [["evaluate", *(["--all"] if all else [])]]
  return _view(runner.start("evaluate", {"all": all}, steps))


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
