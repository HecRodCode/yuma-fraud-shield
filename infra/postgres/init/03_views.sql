CREATE OR REPLACE VIEW v_comparison AS
SELECT
  t.id AS transaction_id,
  t.created_at,
  t.amount,
  t.is_fraud,
  t.fraud_type,
  d.action AS shield_action,
  b.action AS baseline_action,
  EXTRACT(EPOCH FROM b.detected_at - t.created_at) / 60 AS baseline_delay_minutes
FROM transactions t
JOIN decisions d ON d.transaction_id = t.id
JOIN baseline_decisions b ON b.transaction_id = t.id;

GRANT SELECT ON v_comparison TO grafana_ro;
