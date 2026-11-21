import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

from app.core.settings import ARTIFACTS_DIR

STATUS_FILE = ARTIFACTS_DIR / "retrain_status.json"
LOG_FILE = ARTIFACTS_DIR / "retrain.log"


class RetrainRunningError(Exception):
  pass


def _alive(pid: int) -> bool:
  try:
    os.kill(pid, 0)
  except OSError:
    return False
  return True


def _write(state: dict) -> None:
  temporary = STATUS_FILE.with_name(STATUS_FILE.name + ".tmp")
  temporary.write_text(json.dumps(state))
  os.replace(temporary, STATUS_FILE)


def status(log_lines: int = 25) -> dict:
  state = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {"state": "idle"}
  if state.get("state") == "running" and not _alive(state["pid"]):
    state["state"] = "failed"
    _write(state)
  lines = LOG_FILE.read_text().splitlines()[-log_lines:] if LOG_FILE.exists() else []
  return {**state, "log": lines}


def start(use_feedback: bool, trigger: str = "portal") -> dict:
  if status()["state"] == "running":
    raise RetrainRunningError("a training run is already in progress")

  ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
  command = [sys.executable, "-m", "shield_ml.train", "--trigger", trigger]
  if not use_feedback:
    command.append("--no-feedback")
  log = open(LOG_FILE, "w")
  process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy())
  state = {
    "state": "running",
    "pid": process.pid,
    "use_feedback": use_feedback,
    "started_at": datetime.now(timezone.utc).isoformat(),
  }
  _write(state)

  def finish() -> None:
    code = process.wait()
    log.close()
    _write({**state, "state": "finished" if code == 0 else "failed",
            "finished_at": datetime.now(timezone.utc).isoformat()})

  threading.Thread(target=finish, daemon=True).start()
  return status()
