import json

import pandas as pd
import streamlit as st

from lib.db import BASELINE_COLOR, SHIELD_COLOR, query, rows

st.set_page_config(page_title="Transaction explorer", layout="wide")
st.title("Transaction explorer")
st.caption("Search any transaction and see every step behind the decision: reasons, features, rules and audit trail.")

with st.form("filters"):
  a, b, c, d = st.columns(4)
  transaction_id = a.text_input("Transaction id contains")
  customer_id = b.text_input("Customer id")
  actions = c.multiselect("Yuma Shield decision", ["approve", "challenge", "hold", "reject"])
  truth = d.selectbox("Ground truth", ["any", "fraud", "legitimate"])
  e, f, g, h = st.columns(4)
  baseline = e.selectbox("Current engine", ["any", "alert", "approve"])
  disagree = f.checkbox("Only where the engines disagree")
  min_amount = g.number_input("Minimum amount (COP)", min_value=0, value=0, step=50000)
  limit = h.number_input("Max rows", min_value=10, max_value=500, value=100, step=10)
  st.form_submit_button("Search")

conditions, params = ["TRUE"], []
if transaction_id:
  conditions.append("t.id ILIKE %s")
  params.append(f"%{transaction_id}%")
if customer_id:
  conditions.append("t.customer_id = %s")
  params.append(customer_id.strip())
if actions:
  conditions.append("d.action = ANY(%s)")
  params.append(actions)
if truth != "any":
  conditions.append("t.is_fraud = %s")
  params.append(truth == "fraud")
if baseline != "any":
  conditions.append("b.action = %s")
  params.append(baseline)
if disagree:
  conditions.append("((d.action <> 'approve') <> (b.action = 'alert'))")
if min_amount:
  conditions.append("t.amount >= %s")
  params.append(min_amount)

results = query(
  f"""
  SELECT t.id, t.occurred_at, t.customer_id, t.operation_type, t.amount, d.action AS shield,
         d.score, b.action AS baseline, b.rules_fired, t.is_fraud, t.fraud_type
  FROM transactions t
  JOIN decisions d ON d.transaction_id = t.id
  LEFT JOIN baseline_decisions b ON b.transaction_id = t.id
  WHERE {' AND '.join(conditions)}
  ORDER BY t.occurred_at DESC LIMIT %s
  """,
  (*params, limit),
)
st.write(f"{len(results)} transactions")
if results.empty:
  st.stop()

event = st.dataframe(
  results, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row"
)
selected = event.selection.rows
if not selected:
  st.info("Select a row to see the full detail.")
  st.stop()

tx_id = results.iloc[selected[0]]["id"]
tx = rows("SELECT * FROM transactions WHERE id = %s", (tx_id,))[0]
decision = rows("SELECT * FROM decisions WHERE transaction_id = %s", (tx_id,))[0]
base = rows("SELECT * FROM baseline_decisions WHERE transaction_id = %s", (tx_id,))
legacy = rows("SELECT * FROM legacy_alerts WHERE transaction_id = %s", (tx_id,))

st.divider()
st.subheader(f"Transaction {tx_id}")
head = st.columns(5)
head[0].metric("Yuma Shield", decision["action"].upper())
head[1].metric("Risk score", f"{float(decision['score']):.3f}")
head[2].metric("Current engine", "ALERT" if base and base[0]["action"] == "alert" else "APPROVE")
head[3].metric("Ground truth", f"FRAUD ({tx['fraud_type']})" if tx["is_fraud"] else "legitimate")
head[4].metric("Amount", f"COP {tx['amount']:,}")

tabs = st.tabs(["Why this decision", "Features", "Customer context", "Current engine", "Audit trail"])

with tabs[0]:
  st.markdown("**Reasons in plain language**")
  for r in decision["reasons"]:
    icon = "🔺" if r["effect"] == "raises_risk" else "🔻"
    st.write(f"{icon} {r['text']}  ·  impact `{r['impact']:+.2f}`")
  st.markdown("**Hard rules evaluated**")
  if decision["rules"]:
    st.dataframe(pd.DataFrame(decision["rules"]), hide_index=True, width="stretch")
  timings = decision["timings"] or {}
  if timings:
    st.markdown("**Time spent (ms)**")
    st.bar_chart(pd.Series(timings, name="ms"), color=SHIELD_COLOR)
  st.caption(
    f"Model {decision['model_version']} · decision source: {decision['source']} · "
    f"hard rule: {decision['hard_rule'] or 'none'}"
  )

with tabs[1]:
  features = decision["features"]
  if features:
    table = pd.DataFrame({"feature": list(features), "value": list(features.values())})
    st.dataframe(table, hide_index=True, width="stretch", height=520)
    st.caption("These are exactly the values the model received, computed only from data before the operation.")
  else:
    st.info("A hard rule decided this transaction; the model was not used.")

with tabs[2]:
  st.markdown("**Session events in the 48 hours before**")
  events = query(
    """
    SELECT occurred_at, type, result, device_id, ip_department FROM session_events
    WHERE customer_id = %s AND occurred_at BETWEEN %s::timestamptz - INTERVAL '48 hours' AND %s
    ORDER BY occurred_at DESC LIMIT 60
    """,
    (tx["customer_id"], tx["occurred_at"], tx["occurred_at"]),
  )
  st.dataframe(events, hide_index=True, width="stretch")
  st.markdown("**Recent operations by the customer**")
  recent = query(
    """
    SELECT occurred_at, operation_type, amount, destination_id, new_destination, new_device, is_fraud
    FROM transactions WHERE customer_id = %s AND occurred_at <= %s
    ORDER BY occurred_at DESC LIMIT 15
    """,
    (tx["customer_id"], tx["occurred_at"]),
  )
  st.dataframe(recent, hide_index=True, width="stretch")

with tabs[3]:
  if base and base[0]["action"] == "alert":
    fired = base[0]["rules_fired"].split("|")
    catalog = query("SELECT id, name, condition, severity FROM legacy_rules WHERE id = ANY(%s)", (fired,))
    st.markdown(f"<span style='color:{BASELINE_COLOR}'>The current engine alerted this operation.</span>", unsafe_allow_html=True)
    st.dataframe(catalog, hide_index=True, width="stretch")
    st.caption(f"Detected at {base[0]['detected_at']} (15-minute batch), after authorization.")
  else:
    st.write("No legacy rule fired, so the operation was authorized without an alert.")
  if legacy:
    st.markdown("**Historical alert from the case data**")
    st.dataframe(pd.DataFrame(legacy), hide_index=True, width="stretch")

with tabs[4]:
  audit = query(
    "SELECT occurred_at, actor, event, details FROM audit_log WHERE entity_id = %s ORDER BY occurred_at",
    (str(decision["id"]),),
  )
  if audit.empty:
    st.info("No audit trail for this decision (bulk replay decisions are summarized in a single audit entry).")
  else:
    audit["details"] = audit["details"].apply(json.dumps)
    st.dataframe(audit, hide_index=True, width="stretch")
    st.caption("Written by the API when scoring and by the persister when stored; append-only.")
