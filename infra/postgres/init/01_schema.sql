CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  is_merchant BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE session_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id TEXT NOT NULL REFERENCES accounts(id),
  type TEXT NOT NULL
    CHECK (type IN ('login', 'device_change', 'password_change', 'phone_change', 'otp_requested')),
  device TEXT,
  occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_session_events_account_time ON session_events (account_id, occurred_at DESC);
CREATE INDEX idx_session_events_type_time ON session_events (account_id, type, occurred_at DESC);

CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_account TEXT NOT NULL REFERENCES accounts(id),
  target_account TEXT NOT NULL REFERENCES accounts(id),
  amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
  channel TEXT NOT NULL,
  device TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  -- ground truth, only available because the data is synthetic
  is_fraud BOOLEAN NOT NULL DEFAULT FALSE,
  fraud_type TEXT
    CHECK (fraud_type IN ('account_takeover', 'sim_swap', 'mule_account', 'fake_qr'))
);

CREATE INDEX idx_transactions_source_time ON transactions (source_account, created_at DESC);
CREATE INDEX idx_transactions_target_time ON transactions (target_account, created_at DESC);
CREATE INDEX idx_transactions_time ON transactions (created_at DESC);

CREATE TABLE decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id UUID NOT NULL UNIQUE REFERENCES transactions(id),
  score NUMERIC(6, 5) NOT NULL,
  action TEXT NOT NULL
    CHECK (action IN ('approve', 'challenge', 'hold')),
  hard_rule TEXT,
  reasons JSONB NOT NULL,
  latency_ms INT NOT NULL,
  model_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_decisions_action_time ON decisions (action, created_at DESC);

CREATE TABLE baseline_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id UUID NOT NULL UNIQUE REFERENCES transactions(id),
  action TEXT NOT NULL
    CHECK (action IN ('approve', 'alert')),
  rule TEXT
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
  entity_id UUID,
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

CREATE ROLE grafana_ro LOGIN PASSWORD 'grafana_ro';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_ro;
