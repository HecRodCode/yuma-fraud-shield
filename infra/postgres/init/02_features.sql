CREATE OR REPLACE FUNCTION compute_features(
  p_customer TEXT,
  p_destination TEXT,
  p_device TEXT,
  p_at TIMESTAMPTZ
)
RETURNS TABLE (
  out_tx_10m FLOAT8,
  out_tx_60m FLOAT8,
  out_amount_24h FLOAT8,
  avg_amount_30d FLOAT8,
  tx_count_30d FLOAT8,
  failed_logins_24h FLOAT8,
  mins_since_password_change FLOAT8,
  mins_since_sim_change FLOAT8,
  mins_since_device_registration FLOAT8,
  device_age_minutes FLOAT8,
  in_senders_60m FLOAT8,
  in_senders_24h FLOAT8,
  in_amount_24h FLOAT8,
  dest_senders_60m FLOAT8,
  dest_tx_60m FLOAT8,
  dest_senders_24h FLOAT8,
  dest_first_seen_hours FLOAT8,
  dest_age_days FLOAT8
)
LANGUAGE sql STABLE AS $$
  SELECT
    so.n_10m::FLOAT8,
    so.n_60m::FLOAT8,
    so.sum_24h::FLOAT8,
    so.avg_30d::FLOAT8,
    so.n_30d::FLOAT8,
    ev.failed_24h::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_password) / 60)::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_sim) / 60)::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ev.last_registration) / 60)::FLOAT8,
    COALESCE(EXTRACT(EPOCH FROM p_at - dv.first_seen) / 60, 0)::FLOAT8,
    si.senders_60m::FLOAT8,
    si.senders_24h::FLOAT8,
    si.sum_24h::FLOAT8,
    ti.senders_60m::FLOAT8,
    ti.n_60m::FLOAT8,
    ti.senders_24h::FLOAT8,
    (EXTRACT(EPOCH FROM p_at - ti.first_seen) / 3600)::FLOAT8,
    (p_at::DATE - (SELECT joined_on FROM customers WHERE id = p_destination))::FLOAT8
  FROM
    (
      SELECT
        count(*) FILTER (WHERE occurred_at >= p_at - INTERVAL '10 minutes') AS n_10m,
        count(*) FILTER (WHERE occurred_at >= p_at - INTERVAL '60 minutes') AS n_60m,
        COALESCE(sum(amount) FILTER (WHERE occurred_at >= p_at - INTERVAL '24 hours'), 0) AS sum_24h,
        avg(amount) AS avg_30d,
        count(*) AS n_30d
      FROM transactions
      WHERE customer_id = p_customer
        AND occurred_at >= p_at - INTERVAL '30 days'
        AND occurred_at < p_at
    ) so,
    (
      SELECT
        count(*) FILTER (
          WHERE type = 'login' AND result = 'failed' AND occurred_at >= p_at - INTERVAL '24 hours'
        ) AS failed_24h,
        max(occurred_at) FILTER (WHERE type = 'password_change') AS last_password,
        max(occurred_at) FILTER (WHERE type = 'sim_change') AS last_sim,
        max(occurred_at) FILTER (WHERE type = 'device_registration') AS last_registration
      FROM session_events
      WHERE customer_id = p_customer
        AND occurred_at >= p_at - INTERVAL '30 days'
        AND occurred_at < p_at
    ) ev,
    (
      SELECT min(ts) AS first_seen FROM (
        SELECT min(occurred_at) AS ts FROM session_events
        WHERE customer_id = p_customer AND device_id = p_device AND occurred_at < p_at
        UNION ALL
        SELECT min(occurred_at) FROM transactions
        WHERE customer_id = p_customer AND device_id = p_device AND occurred_at < p_at
      ) seen
    ) dv,
    (
      SELECT
        COALESCE(sum(amount), 0) AS sum_24h,
        count(DISTINCT customer_id) AS senders_24h,
        count(DISTINCT customer_id) FILTER (WHERE occurred_at >= p_at - INTERVAL '60 minutes') AS senders_60m
      FROM transactions
      WHERE destination_id = p_customer
        AND occurred_at >= p_at - INTERVAL '24 hours'
        AND occurred_at < p_at
    ) si,
    (
      SELECT
        count(DISTINCT customer_id) FILTER (WHERE occurred_at >= p_at - INTERVAL '60 minutes') AS senders_60m,
        count(*) FILTER (WHERE occurred_at >= p_at - INTERVAL '60 minutes') AS n_60m,
        count(DISTINCT customer_id) FILTER (WHERE occurred_at >= p_at - INTERVAL '24 hours') AS senders_24h,
        (SELECT min(occurred_at) FROM transactions
          WHERE destination_id = p_destination AND occurred_at < p_at) AS first_seen
      FROM transactions
      WHERE destination_id = p_destination
        AND occurred_at >= p_at - INTERVAL '24 hours'
        AND occurred_at < p_at
    ) ti
$$;
