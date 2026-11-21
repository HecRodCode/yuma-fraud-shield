import numpy as np
import pandas as pd

SENSITIVE = ("department", "age_range")
MIN_GROUP_LEGIT = 200


def audit(test: pd.DataFrame, actions: np.ndarray) -> dict:
  df = test.assign(action=actions)
  df["blocked"] = df["action"].isin(["hold", "reject"])
  df["flagged"] = df["action"] != "approve"
  report = {}
  for attribute in SENSITIVE:
    rows = []
    for group, part in df.groupby(attribute):
      legit = part[~part["is_fraud"]]
      fraud = part[part["is_fraud"]]
      if len(legit) < MIN_GROUP_LEGIT:
        continue
      rows.append(
        {
          "group": str(group),
          "transactions": int(len(part)),
          "legit_blocked_pct": round(100 * legit["blocked"].mean(), 2),
          "legit_flagged_pct": round(100 * legit["flagged"].mean(), 2),
          "fraud_detected_pct": round(100 * fraud["flagged"].mean(), 2) if len(fraud) else None,
          "fraud_cases": int(len(fraud)),
        }
      )
    blocked = [r["legit_blocked_pct"] for r in rows]
    flagged = [r["legit_flagged_pct"] for r in rows]
    report[attribute] = {
      "groups": sorted(rows, key=lambda r: r["group"]),
      "legit_blocked_max_min_gap_pp": round(max(blocked) - min(blocked), 2) if rows else None,
      "legit_flagged_max_min_gap_pp": round(max(flagged) - min(flagged), 2) if rows else None,
    }
  return report
