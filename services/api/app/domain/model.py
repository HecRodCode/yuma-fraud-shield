import json
import math
import time

import numpy as np
import xgboost as xgb

from app.core.settings import ARTIFACTS_DIR, CONFIG_DIR
from app.domain.rules import Rules, load_rules
from app.domain.thresholds import Thresholds, load_thresholds

CHECK_INTERVAL_SECONDS = 2.0
WATCHED = (
  ARTIFACTS_DIR / "model.json",
  CONFIG_DIR / "rules.yaml",
  CONFIG_DIR / "thresholds.yaml",
)


class ModelNotReadyError(Exception):
  pass


class Scorer:
  def __init__(self) -> None:
    self.booster: xgb.Booster | None = None
    self.features: list[str] = []
    self.version = ""
    self.rules = Rules()
    self.thresholds = Thresholds(0.3, 0.8, 0.95)
    self._stamp: tuple = ()
    self._checked = 0.0
    self.refresh(force=True)

  @property
  def ready(self) -> bool:
    return self.booster is not None

  def refresh(self, force: bool = False) -> None:
    now = time.monotonic()
    if not force and now - self._checked < CHECK_INTERVAL_SECONDS:
      return
    self._checked = now
    stamp = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in WATCHED)
    if stamp == self._stamp:
      return
    self._stamp = stamp
    self.rules = load_rules()
    self.thresholds = load_thresholds()
    meta_path = ARTIFACTS_DIR / "meta.json"
    if (ARTIFACTS_DIR / "model.json").exists() and meta_path.exists():
      meta = json.loads(meta_path.read_text())
      booster = xgb.Booster()
      booster.load_model(str(ARTIFACTS_DIR / "model.json"))
      self.features = meta["features"]
      self.version = meta["version"]
      self.booster = booster

  def predict(self, vector: list[float]) -> tuple[float, list[float]]:
    if not self.ready:
      raise ModelNotReadyError("model not loaded, run training first")
    matrix = xgb.DMatrix(np.array([vector]), feature_names=self.features, missing=math.nan)
    contribs = self.booster.predict(matrix, pred_contribs=True)[0]
    margin = float(contribs.sum())
    return 1.0 / (1.0 + math.exp(-margin)), [float(c) for c in contribs[:-1]]
