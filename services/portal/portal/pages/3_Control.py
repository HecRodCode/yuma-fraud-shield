import os

import httpx
import pandas as pd
import streamlit as st

from lib.db import SHIELD_COLOR, load_json, query

CONTROL_URL = os.environ.get("CONTROL_URL", "http://localhost:8001")
API_URL = os.environ.get("API_URL", "http://localhost:8000")
SANDBOX_URL = os.environ.get("SANDBOX_URL", "http://localhost:8090")

st.set_page_config(page_title="Control", layout="wide")
st.title("Control and model")


def probe(url: str) -> str:
  try:
    return "up" if httpx.get(url, timeout=2).status_code == 200 else "error"
  except httpx.HTTPError:
    return "down"


def launch(path: str, body: dict) -> None:
  try:
    response = httpx.post(f"{CONTROL_URL}{path}", json=body, timeout=10)
    response.raise_for_status()
    st.session_state["job"] = response.json()["id"]
    st.success(f"Job {st.session_state['job']} started")
  except httpx.HTTPError as error:
    st.error(f"Could not start the job: {error}")


health = st.columns(3)
health[0].metric("Scoring API", probe(f"{API_URL}/health"))
health[1].metric("Simulator control", probe(f"{CONTROL_URL}/health"))
health[2].metric("Case sandbox", probe(f"{SANDBOX_URL}/v1/salud"))

st.subheader("Launch")
live, attack, sandbox = st.columns(3)
with live:
  st.markdown("**Legitimate traffic**")
  tps = st.slider("Transactions per second", 1, 100, 10)
  duration = st.slider("Duration (s)", 5, 120, 30)
  if st.button("Start traffic"):
    launch("/jobs/live", {"tps": tps, "duration": duration})
with attack:
  st.markdown("**Fraud attack**")
  kind = st.selectbox("Type", ["account_takeover", "sim_swap", "social_engineering", "qr_scam", "mule_account"])
  speedup = st.slider("Speed (virtual s per real s)", 10, 3600, 600)
  if st.button("Launch attack", type="primary"):
    launch("/jobs/attack", {"type": kind, "speedup": speedup})
with sandbox:
  st.markdown("**Official sandbox run**")
  start = st.text_input("Decide transactions from", "2026-10-01 00:00:00")
  limit = st.number_input("Limit (0 = all)", min_value=0, value=0, step=1000)
  if st.button("Run sandbox"):
    launch("/jobs/sandbox", {"start": start, "reset": True, "limit": int(limit) or None})


@st.fragment(run_every=3)
def jobs() -> None:
  st.subheader("Jobs")
  try:
    listing = httpx.get(f"{CONTROL_URL}/jobs", timeout=5).json()
  except httpx.HTTPError:
    st.warning("Control service unavailable")
    return
  if not listing:
    st.caption("No jobs yet.")
    return
  st.dataframe(
    pd.DataFrame(listing)[["id", "type", "status", "started_at"]], hide_index=True, width="stretch"
  )
  job_id = st.session_state.get("job", listing[0]["id"])
  detail = httpx.get(f"{CONTROL_URL}/jobs/{job_id}", timeout=5).json()
  st.markdown(f"**Log of job {job_id}** ({detail['status']})")
  st.code("\n".join(detail["log"]) or "(empty)", language="text")


jobs()

st.subheader("Live scoring latency")
latency = query(
  """
  SELECT count(*) AS decisions,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
  FROM decisions WHERE source = 'live' AND latency_ms IS NOT NULL
  """
).iloc[0]
cols = st.columns(4)
cols[0].metric("Decisions measured", f"{int(latency.decisions):,}")
for column, key in zip(cols[1:], ("p50", "p95", "p99")):
  column.metric(key, "n/a" if pd.isna(latency[key]) else f"{latency[key]:.1f} ms")
st.caption("Time inside the API (features + model). Goal: under 300 ms.")

meta = load_json("meta.json")
if meta:
  st.subheader("Model")
  st.write(f"Version `{meta['version']}` · trained on May–August, thresholds from September, tested on October.")
  test = meta["metrics"]["test"]
  cols = st.columns(5)
  cols[0].metric("Fraud detected", f"{test['fraud_detected_pct']} %")
  cols[1].metric("False positives", f"{test['false_positive_pct']} %")
  cols[2].metric("Legit blocked", f"{test['legit_blocked_pct']} %")
  cols[3].metric("Legit challenged", f"{test['legit_challenged_pct']} %")
  cols[4].metric("ROC AUC", f"{test['roc_auc']:.4f}")
  top = pd.DataFrame(meta["top_features"], columns=["feature", "mean |SHAP|"]).set_index("feature")
  st.markdown("**What drives decisions (global SHAP importance)**")
  st.bar_chart(top, color=SHIELD_COLOR)

fairness = load_json("fairness.json")
if fairness:
  st.subheader("Fairness audit")
  st.caption("Department and age range are never model inputs; they are only used here to check for disparities.")
  for attribute, report in fairness.items():
    st.markdown(
      f"**{attribute}** · gap in legitimate customers blocked: "
      f"{report['legit_blocked_max_min_gap_pp']} pp · flagged: {report['legit_flagged_max_min_gap_pp']} pp"
    )
    st.dataframe(pd.DataFrame(report["groups"]), hide_index=True, width="stretch")
