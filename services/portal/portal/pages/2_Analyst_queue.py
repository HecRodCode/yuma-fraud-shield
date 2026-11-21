import json

import streamlit as st

from lib.db import execute, query, rows

st.set_page_config(page_title="Analyst queue", layout="wide")
st.title("Analyst queue")
st.caption("Held and rejected operations, ordered by risk. Only an analyst can confirm fraud.")

analyst = st.sidebar.text_input("Analyst name", value="analyst-1")
reveal = st.sidebar.checkbox("Reveal ground truth (demo only)")

stats = rows(
  "SELECT status, count(*) AS n FROM alerts GROUP BY status"
)
counts = {r["status"]: r["n"] for r in stats}
c = st.columns(3)
c[0].metric("Pending", f"{counts.get('pending', 0):,}")
c[1].metric("Fraud confirmed", f"{counts.get('fraud_confirmed', 0):,}")
c[2].metric("Released", f"{counts.get('released', 0):,}")

queue = query(
  """
  SELECT a.id AS alert_id, d.score, d.action, t.id AS transaction_id, t.occurred_at,
         t.customer_id, t.operation_type, t.amount, t.is_fraud, t.fraud_type,
         d.reasons
  FROM alerts a
  JOIN decisions d ON d.id = a.decision_id
  JOIN transactions t ON t.id = d.transaction_id
  WHERE a.status = 'pending'
  ORDER BY d.score DESC, t.occurred_at DESC LIMIT 100
  """
)
if queue.empty:
  st.success("No pending alerts.")
  st.stop()

view = queue.drop(columns=["alert_id", "reasons"] + ([] if reveal else ["is_fraud", "fraud_type"]))
event = st.dataframe(
  view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row"
)
if not event.selection.rows:
  st.info("Select an alert to review it.")
  st.stop()

alert = queue.iloc[event.selection.rows[0]]
st.divider()
st.subheader(f"Alert on transaction {alert.transaction_id}")
st.write(
  f"Customer **{alert.customer_id}** · {alert.operation_type} · **COP {alert.amount:,}** · "
  f"decision **{alert.action}** · risk score **{float(alert.score):.3f}**"
)
st.markdown("**Why it was flagged**")
for r in alert.reasons:
  st.write(("🔺 " if r["effect"] == "raises_risk" else "🔻 ") + r["text"])

col_a, col_b = st.columns(2)


def label(verdict: str, status: str) -> None:
  execute(
    [
      ("INSERT INTO labels (transaction_id, alert_id, verdict, source, analyst) "
       "VALUES (%s, %s, %s, 'analyst', %s) ON CONFLICT (transaction_id) DO UPDATE "
       "SET verdict = EXCLUDED.verdict, analyst = EXCLUDED.analyst, alert_id = EXCLUDED.alert_id",
       (alert.transaction_id, alert.alert_id, verdict, analyst)),
      ("UPDATE alerts SET status = %s WHERE id = %s", (status, alert.alert_id)),
      ("INSERT INTO audit_log (entity, entity_id, event, details, actor) VALUES ('alert', %s, %s, %s, %s)",
       (str(alert.alert_id), "reviewed", json.dumps({"verdict": verdict}), f"analyst:{analyst}")),
    ]
  )
  st.rerun()


if col_a.button("Confirm fraud", type="primary", width="stretch"):
  label("fraud", "fraud_confirmed")
if col_b.button("Release (false positive)", width="stretch"):
  label("legitimate", "released")
st.caption(
  "Each verdict is stored as a label and in the audit log. Labels feed the next training run "
  "(labels on October transactions are kept but excluded from training so the test stays clean)."
)
