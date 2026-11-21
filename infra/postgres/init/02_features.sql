CREATE OR REPLACE FUNCTION compute_features(
  p_source TEXT,
  p_target TEXT,
  p_amount NUMERIC,
  p_channel TEXT,
  p_device TEXT,
  p_at TIMESTAMPTZ
)
RETURNS TABLE (
  amount FLOAT8,
  amount_ratio FLOAT8,
  src_tx_10m FLOAT8,
  src_amount_10m FLOAT8,
  src_age_hours FLOAT8,
  src_inflow_24h FLOAT8,
  src_inflow_senders_60m FLOAT8,
  device_age_minutes FLOAT8,
  mins_since_password_change FLOAT8,
  mins_since_phone_change FLOAT8,
  mins_since_device_change FLOAT8,
  otp_15m FLOAT8,
  hour_of_day FLOAT8,
  tgt_age_hours FLOAT8,
  tgt_is_merchant FLOAT8,
  tgt_senders_60m FLOAT8,
  tgt_tx_60m FLOAT8,
  tgt_avg_amount_60m FLOAT8,
  tgt_inflow_24h FLOAT8,
  tgt_outflow_24h FLOAT8,
  pair_first_time FLOAT8
)
LANGUAGE sql STABLE AS $$
  SELECT
    p_amount::FLOAT8,
    (p_amount / NULLIF(so.avg_30d, 0))::FLOAT8,
    so.n_10m::FLOAT8,
    so.sum_10m::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - (SELECT created_at FROM accounts WHERE id = p_source)) / 3600)::FLOAT8,
    si.sum_24h::FLOAT8,
    si.senders_60m::FLOAT8,
    COALESCE(EXTRACT(EPOCH FROM p_at - dv.first_seen) / 60, 0)::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_password) / 60)::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_phone) / 60)::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_device) / 60)::FLOAT8,
    ev.otp_15m::FLOAT8,
    EXTRACT(HOUR FROM p_at AT TIME ZONE 'America/Bogota')::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - (SELECT created_at FROM accounts WHERE id = p_target)) / 3600)::FLOAT8,
    (SELECT CASE WHEN is_merchant THEN 1 ELSE 0 END FROM accounts WHERE id = p_target)::FLOAT8,
    ti.senders_60m::FLOAT8,
    ti.n_60m::FLOAT8,
    ti.avg_60m::FLOAT8,
    ti.sum_24h::FLOAT8,
    tout.sum_24h::FLOAT8,
    (CASE WHEN EXISTS (
      SELECT 1 FROM transactions
      WHERE source_account = p_source AND target_account = p_target AND created_at < p_at
    ) THEN 0 ELSE 1 END)::FLOAT8
  FROM
    (
      SELECT
        avg(amount) AS avg_30d,
        count(*) FILTER (WHERE created_at >= p_at - INTERVAL '10 minutes') AS n_10m,
        COALESCE(sum(amount) FILTER (WHERE created_at >= p_at - INTERVAL '10 minutes'), 0) AS sum_10m
      FROM transactions
      WHERE source_account = p_source
        AND created_at >= p_at - INTERVAL '30 days'
        AND created_at < p_at
    ) so,
    (
      SELECT
        COALESCE(sum(amount), 0) AS sum_24h,
        count(DISTINCT source_account) FILTER (WHERE created_at >= p_at - INTERVAL '60 minutes') AS senders_60m
      FROM transactions
      WHERE target_account = p_source
        AND created_at >= p_at - INTERVAL '24 hours'
        AND created_at < p_at
    ) si,
    (
      SELECT
        count(DISTINCT source_account) FILTER (WHERE created_at >= p_at - INTERVAL '60 minutes') AS senders_60m,
        count(*) FILTER (WHERE created_at >= p_at - INTERVAL '60 minutes') AS n_60m,
        avg(amount) FILTER (WHERE created_at >= p_at - INTERVAL '60 minutes') AS avg_60m,
        COALESCE(sum(amount), 0) AS sum_24h
      FROM transactions
      WHERE target_account = p_target
        AND created_at >= p_at - INTERVAL '24 hours'
        AND created_at < p_at
    ) ti,
    (
      SELECT COALESCE(sum(amount), 0) AS sum_24h
      FROM transactions
      WHERE source_account = p_target
        AND created_at >= p_at - INTERVAL '24 hours'
        AND created_at < p_at
    ) tout,
    (
      SELECT
        max(occurred_at) FILTER (WHERE type = 'password_change') AS last_password,
        max(occurred_at) FILTER (WHERE type = 'phone_change') AS last_phone,
        max(occurred_at) FILTER (WHERE type = 'device_change') AS last_device,
        count(*) FILTER (
          WHERE type = 'otp_requested' AND occurred_at >= p_at - INTERVAL '15 minutes'
        ) AS otp_15m
      FROM session_events
      WHERE account_id = p_source
        AND occurred_at >= p_at - INTERVAL '30 days'
        AND occurred_at <= p_at
    ) ev,
    (
      SELECT min(ts) AS first_seen FROM (
        SELECT min(occurred_at) AS ts FROM session_events
        WHERE account_id = p_source AND device = p_device AND occurred_at <= p_at
        UNION ALL
        SELECT min(created_at) FROM transactions
        WHERE source_account = p_source AND device = p_device AND created_at < p_at
      ) seen
    ) dv
$$;
