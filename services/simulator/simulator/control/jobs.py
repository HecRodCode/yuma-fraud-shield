import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
  id: str
  type: str
  params: dict
  status: str = "running"
  started_at: str = ""
  ended_at: str | None = None
  log: list[str] = field(default_factory=list)


class JobRunner:
  def __init__(self) -> None:
    self.jobs: dict[str, Job] = {}
    self._lock = threading.Lock()

  def running(self, type_: str | None = None) -> bool:
    return any(
      j.status == "running" and (type_ is None or j.type == type_) for j in self.jobs.values()
    )

  def start(self, type_: str, params: dict, steps: list[list[str]]) -> Job:
    job = Job(
      id=uuid.uuid4().hex[:8],
      type=type_,
      params=params,
      started_at=datetime.now(timezone.utc).isoformat(),
    )
    with self._lock:
      self.jobs[job.id] = job
    threading.Thread(target=self._run, args=(job, steps), daemon=True).start()
    return job

  def _run(self, job: Job, steps: list[list[str]]) -> None:
    for step in steps:
      job.log.append("$ simulator " + " ".join(step))
      process = subprocess.Popen(
        [sys.executable, "-m", "simulator", *step],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
      )
      for line in process.stdout:
        job.log.append(line.rstrip())
      if process.wait() != 0:
        job.status = "failed"
        job.ended_at = datetime.now(timezone.utc).isoformat()
        return
    job.status = "finished"
    job.ended_at = datetime.now(timezone.utc).isoformat()
