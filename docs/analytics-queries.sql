-- =============================================================================
-- ET-79: Launch-funnel analytics queries
-- =============================================================================
-- One-off SQL snippets for post-launch cohort analysis. Run against the
-- production Postgres replica (read-only user recommended).
--
-- Prerequisites:
--   * api_keys.first_api_call_at  (added by migration g8h9i0j1k2l3)
--   * api_call_logs.api_key_hash  (first 16 chars of sha256(raw_key))
--   * api_keys.key_hash           (full sha256 of raw_key)
--
-- Users are identified by ApiKey (this repo has no separate User model —
-- ApiKey carries the email + tier, so each row is one "user").
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Query 1: Weekly-cohort 7-day retention
-- -----------------------------------------------------------------------------
-- For each weekly signup cohort, what % of users made at least 2 API calls
-- within 7 days of signing up? This is the headline onboarding-retention
-- metric driving launch-funnel decisions. Replace the default 7-day / 2-call
-- thresholds inline below if the product definition of "retained" changes.
--
-- Output columns:
--   cohort_week       ISO week (Mon) the user signed up
--   signups           Users in that cohort
--   retained_7d       Users with >=2 distinct call-days within 7 days of signup
--   retention_pct     100.0 * retained_7d / signups
WITH cohorts AS (
    SELECT
        DATE_TRUNC('week', ak.created_at)         AS cohort_week,
        ak.id                                     AS api_key_id,
        ak.created_at                             AS signup_at,
        SUBSTRING(ak.key_hash FROM 1 FOR 16)      AS key_prefix
    FROM api_keys ak
),
calls_in_window AS (
    SELECT
        c.cohort_week,
        c.api_key_id,
        COUNT(*) AS calls_7d
    FROM cohorts c
    JOIN api_call_logs l
      ON l.api_key_hash = c.key_prefix
     AND l.created_at >= c.signup_at
     AND l.created_at <  c.signup_at + INTERVAL '7 days'
    GROUP BY c.cohort_week, c.api_key_id
)
SELECT
    c.cohort_week,
    COUNT(DISTINCT c.api_key_id)                                  AS signups,
    COUNT(DISTINCT CASE WHEN w.calls_7d >= 2 THEN c.api_key_id END) AS retained_7d,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN w.calls_7d >= 2 THEN c.api_key_id END)
              / NULLIF(COUNT(DISTINCT c.api_key_id), 0),
        2
    ) AS retention_pct
FROM cohorts c
LEFT JOIN calls_in_window w USING (api_key_id, cohort_week)
GROUP BY c.cohort_week
ORDER BY c.cohort_week DESC;


-- -----------------------------------------------------------------------------
-- Query 2: Time-to-first-call distribution (ET-79 health check)
-- -----------------------------------------------------------------------------
-- Sanity-check the middleware: how long do users take to make their first
-- API call? Large p95 / unbounded maxes indicate onboarding friction.
SELECT
    COUNT(*) FILTER (WHERE first_api_call_at IS NOT NULL) AS activated_users,
    COUNT(*) FILTER (WHERE first_api_call_at IS NULL)     AS unactivated_users,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (first_api_call_at - created_at))) AS p50_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (first_api_call_at - created_at))) AS p95_seconds
FROM api_keys
WHERE first_api_call_at IS NOT NULL;
