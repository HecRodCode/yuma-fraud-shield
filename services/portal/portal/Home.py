import os

import pandas as pd
import streamlit as st

from lib.db import BASELINE_COLOR, SHIELD_COLOR, load_json, pct, query, show

st.set_page_config(page_title="Yuma Shield", layout="wide")
st.title("Yuma Shield")
st.caption("Fraud scoring before authorization, compared with the current rules engine on the same transactions.")

PERIODS = {
  "October 2026 (test period, never used for training)": ("2026-10-01 00:00-05", "2026-11-01 00:00-05"),
  "Simulated traffic and attacks (after October)": ("2026-11-01 00:00-05", "2100-01-01 00:00-05"),
  "Everything evaluated": ("1970-01-01 00:00-05", "2100-01-01 00:00-05"),
}
period = st.selectbox("Period", list(PERIODS))
start, end = PERIODS[period]

totals = query(
  """
  SELECT
    count(*) AS transactions,
    count(*) FILTER (WHERE NOT is_fraud) AS legit,
    count(*) FILTER (WHERE is_fraud) AS fraud,
    count(*) FILTER (WHERE is_fraud AND shield_flagged) AS shield_detected,
    count(*) FILTER (WHERE is_fraud AND baseline_action = 'alert') AS base_detected,
    count(*) FILTER (WHERE shield_blocked AND NOT is_fraud) AS shield_fp,
    count(*) FILTER (WHERE baseline_action = 'alert' AND NOT is_fraud) AS base_fp,
    count(*) FILTER (WHERE baseline_action = 'alert') AS base_alerts,
    count(*) FILTER (WHERE shield_blocked) AS shield_blocked,
    count(*) FILTER (WHERE shield_action = 'challenge' AND NOT is_fraud) AS shield_challenged_legit,
    COALESCE(sum(amount) FILTER (WHERE is_fraud), 0) AS fraud_amount,
    COALESCE(sum(amount) FILTER (WHERE is_fraud AND shield_flagged), 0) AS shield_amount,
    COALESCE(sum(amount) FILTER (WHERE is_fraud AND baseline_action = 'alert'), 0) AS base_amount
  FROM v_comparison WHERE created_at >= %s AND created_at < %s
  """,
  (start, end),
).iloc[0]

if totals["transactions"] == 0:
  st.info("No transactions with decisions from both engines in this period yet.")
  st.stop()

shield = {
  "False positives (sandbox definition)": pct(totals.shield_fp, totals.shield_detected + totals.shield_fp),
  "Fraud detected": pct(totals.shield_detected, totals.fraud),
  "Fraud amount covered": pct(totals.shield_amount, totals.fraud_amount),
  "Legitimate customers blocked": pct(totals.shield_fp, totals.legit),
  "Legitimate customers challenged": pct(totals.shield_challenged_legit, totals.legit),
  "Alerts for analysts": int(totals.shield_blocked),
}
baseline = {
  "False positives (sandbox definition)": pct(totals.base_fp, totals.base_alerts),
  "Fraud detected": pct(totals.base_detected, totals.fraud),
  "Fraud amount covered": pct(totals.base_amount, totals.fraud_amount),
  "Legitimate customers blocked": pct(totals.base_fp, totals.legit),
  "Legitimate customers challenged": 0.0,
  "Alerts for analysts": int(totals.base_alerts),
}

st.markdown(
  f"**{int(totals.transactions):,}** transactions · **{int(totals.fraud):,}** fraud cases · "
  f"**{int(totals.legit):,}** legitimate"
)
left, right = st.columns(2)
for column, name, values, color, note in (
  (left, "Yuma Shield", shield, SHIELD_COLOR, "Decides before authorizing, in milliseconds."),
  (right, "Current engine (12 rules)", baseline, BASELINE_COLOR, "Alerts after authorizing, in 15-minute batches."),
):
  with column:
    st.markdown(f"<h3 style='color:{color};margin-bottom:0'>{name}</h3>", unsafe_allow_html=True)
    st.caption(note)
    for label, value in values.items():
      if label == "Alerts for analysts":
        st.metric(label, f"{value:,}")
      else:
        st.metric(label, show(value))
st.caption("Goal from the case: false positives below 60 % without letting more fraud through.")

st.subheader("Fraud detected by type")
by_type = query(
  """
  SELECT fraud_type,
    count(*) AS cases,
    round(100.0 * count(*) FILTER (WHERE shield_flagged) / count(*), 1) AS shield,
    round(100.0 * count(*) FILTER (WHERE baseline_action = 'alert') / count(*), 1) AS baseline
  FROM v_comparison WHERE is_fraud AND created_at >= %s AND created_at < %s
  GROUP BY fraud_type ORDER BY fraud_type
  """,
  (start, end),
)
if not by_type.empty:
  by_type[["shield", "baseline"]] = by_type[["shield", "baseline"]].astype(float)
  chart = by_type.set_index("fraud_type")[["shield", "baseline"]].rename(
    columns={"shield": "Yuma Shield", "baseline": "Current engine"}
  )
  st.bar_chart(chart, color=[SHIELD_COLOR, BASELINE_COLOR], y_label="% detected")
  st.dataframe(by_type.rename(columns={"shield": "Yuma Shield %", "baseline": "Current engine %"}),
               hide_index=True, width="stretch")

report = load_json("sandbox_report.json")
if report:
  st.subheader("Official sandbox indicators")
  m = report["sandbox_metrics"]
  cols = st.columns(5)
  cols[0].metric("Decided", f"{m['transacciones_decididas']:,}")
  cols[1].metric("Fraud detected", show(m["fraude_detectado_pct"]))
  cols[2].metric("False positives", show(m["falsos_positivos_pct"]))
  cols[3].metric("Latency p50 / p99", f"{m['latencia_ms_p50']:.0f} / {m['latencia_ms_p99']:.0f} ms")
  cols[4].metric("Challenges", f"{m['desafios']:,}")
  st.caption(f"Computed by the case sandbox over transactions from {report['start']}. Latency includes 32 concurrent requests.")

st.subheader("Latest decisions")
latest = query(
  """
  SELECT created_at, transaction_id, customer_id, operation_type, amount, shield_action,
         baseline_action, baseline_rules, is_fraud, fraud_type
  FROM v_comparison WHERE created_at >= %s AND created_at < %s
  ORDER BY created_at DESC LIMIT 100
  """,
  (start, end),
)
st.dataframe(latest, hide_index=True, width="stretch")
