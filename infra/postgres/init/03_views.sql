CREATE OR REPLACE VIEW v_comparison AS
SELECT
  t.id AS transaction_id,
  t.occurred_at AS created_at,
  t.customer_id,
  t.operation_type,
  t.amount,
  t.is_fraud,
  t.fraud_type,
  d.action AS shield_action,
  d.action IN ('hold', 'reject') AS shield_blocked,
  d.action <> 'approve' AS shield_flagged,
  b.action AS baseline_action,
  b.rules_fired AS baseline_rules,
  EXTRACT(EPOCH FROM b.detected_at - t.occurred_at) / 60 AS baseline_delay_minutes
FROM transactions t
JOIN decisions d ON d.transaction_id = t.id
JOIN baseline_decisions b ON b.transaction_id = t.id;

GRANT SELECT ON v_comparison TO grafana_ro;
