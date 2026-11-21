from dataclasses import dataclass

import yaml

from app.core.settings import CONFIG_DIR


@dataclass
class Thresholds:
  low_max: float
  high_min: float

  def decide(self, score: float) -> str:
    if score >= self.high_min:
      return "hold"
    if score >= self.low_max:
      return "challenge"
    return "approve"


def load_thresholds() -> Thresholds:
  data = yaml.safe_load((CONFIG_DIR / "thresholds.yaml").read_text())["score"]
  return Thresholds(low_max=float(data["low_max"]), high_min=float(data["high_min"]))
