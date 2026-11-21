DROP TABLE IF EXISTS
  labels, alerts, baseline_decisions, decisions, legacy_alerts, legacy_rules,
  transactions, session_events, customers, audit_log, accounts
  CASCADE;
DROP FUNCTION IF EXISTS audit_log_immutable() CASCADE;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE customers (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  department TEXT,
  age_range TEXT,
  joined_on DATE NOT NULL,
  confirmed_mule BOOLEAN NOT NULL DEFAULT FALSE,
  onboarding_channel TEXT
);

CREATE TABLE session_events (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  type TEXT NOT NULL
    CHECK (type IN ('login', 'device_registration', 'password_change', 'sim_change')),
  device_id TEXT,
  os TEXT,
  ip_department TEXT,
  result TEXT NOT NULL
    CHECK (result IN ('success', 'failed')),
  occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_session_events_customer_time ON session_events (customer_id, occurred_at DESC);
CREATE INDEX idx_session_events_type_time ON session_events (customer_id, type, occurred_at DESC);

CREATE TABLE transactions (
  id TEXT PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  operation_type TEXT NOT NULL
    CHECK (operation_type IN (
      'instant_transfer', 'qr_payment', 'bill_payment', 'correspondent_withdrawal',
      'atm_withdrawal', 'mobile_topup', 'virtual_card_purchase'
    )),
  channel TEXT NOT NULL,
  amount BIGINT NOT NULL CHECK (amount > 0),
  balance_before BIGINT NOT NULL,
  destination_id TEXT NOT NULL,
  destination_type TEXT NOT NULL,
  new_destination BOOLEAN NOT NULL,
  device_id TEXT,
  new_device BOOLEAN NOT NULL,
  password_change_24h BOOLEAN NOT NULL,
  sim_change_48h BOOLEAN NOT NULL,
  ip_department TEXT,
  ip_department_mismatch BOOLEAN NOT NULL,
  account_age_days INT NOT NULL,
  -- ground truth from the case dataset, never available at scoring time
  is_fraud BOOLEAN NOT NULL DEFAULT FALSE,
  fraud_type TEXT
    CHECK (fraud_type IN (
      'account_takeover', 'sim_swap', 'social_engineering', 'qr_scam', 'mule_account'
    )),
  source TEXT NOT NULL DEFAULT 'dataset'
    CHECK (source IN ('dataset', 'simulated', 'live'))
);

CREATE INDEX idx_transactions_customer_time ON transactions (customer_id, occurred_at DESC);
CREATE INDEX idx_transactions_destination_time ON transactions (destination_id, occurred_at DESC);
CREATE INDEX idx_transactions_time ON transactions (occurred_at DESC);

CREATE TABLE legacy_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  condition TEXT,
  severity TEXT NOT NULL,
  target_fraud TEXT,
  last_modified DATE
);

CREATE TABLE legacy_alerts (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  customer_id TEXT NOT NULL,
  alerted_at TIMESTAMPTZ NOT NULL,
  rules_fired TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  review_minutes INT,
  analyst_decision TEXT,
  action TEXT
);

CREATE TABLE decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(id),
  score NUMERIC(6, 5) NOT NULL,
  action TEXT NOT NULL
    CHECK (action IN ('approve', 'challenge', 'hold', 'reject')),
  hard_rule TEXT,
  reasons JSONB NOT NULL,
  features JSONB,
  rules JSONB,
  timings JSONB,
  latency_ms NUMERIC(8, 2),
  model_version TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'live'
    CHECK (source IN ('live', 'replay')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_decisions_action_time ON decisions (action, created_at DESC);
CREATE INDEX idx_decisions_source_time ON decisions (source, created_at DESC);

CREATE TABLE baseline_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(id),
  action TEXT NOT NULL
    CHECK (action IN ('approve', 'alert')),
  rules_fired TEXT,
  details JSONB,
  detected_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id UUID NOT NULL UNIQUE REFERENCES decisions(id),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'fraud_confirmed', 'released')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_status_time ON alerts (status, created_at);

CREATE TABLE labels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id UUID NOT NULL UNIQUE REFERENCES alerts(id),
  verdict TEXT NOT NULL
    CHECK (verdict IN ('fraud', 'legitimate')),
  analyst TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  entity TEXT NOT NULL,
  entity_id TEXT,
  event TEXT NOT NULL,
  details JSONB,
  actor TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_entity ON audit_log (entity, entity_id);

CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_log_immutable
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    CREATE ROLE grafana_ro LOGIN PASSWORD 'grafana_ro';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_ro;
