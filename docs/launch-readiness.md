# Launch Readiness Checklist

Pre-launch verification for the emissions-tracker production deployment on Railway.
Run every check below and fill in the `Result` line before cutting over DNS / publishing
the press release. All checks are gate-able — any FAIL blocks launch.

**Target environment:** `https://emissions-tracker-production.up.railway.app`

---

## 1. Stress test

**Verifies:** the API absorbs journalist-spike traffic (~100 req/s sustained for 60s)
across the two hottest endpoints without returning any 5xx errors.

**How to run:**
```bash
chmod +x scripts/launch-stress-test.sh
scripts/launch-stress-test.sh
```
Defaults to the production Railway URL. Pass an alternate base URL as arg 1 to
point the test elsewhere (e.g. staging).

**Pass criteria:**
- 0 5xx errors across both endpoints.
- 100% of requests return 2xx (some 429 tolerated — see check 5).
- p95 latency under 1.5s on both endpoints.
- Script exits 0.

**Result:** TBD (run before 2026-04-18)

---

## 2. Cold-start latency

**Verifies:** a cold Railway container can serve the root endpoint in under 3
seconds after idle sleep, so the first journalist to hit us after a quiet period
does not see a timeout.

**How to run:**
1. Leave the service untouched for at least 15 minutes.
2. Run:
   ```bash
   curl -o /dev/null -s -w "total=%{time_total}s connect=%{time_connect}s\n" \
     https://emissions-tracker-production.up.railway.app/
   ```

**Pass criteria:** `total` < 3.0s on the first request after idle.

**Result:** TBD

---

## 3. Database connectivity

**Verifies:** the `/ready` probe reports a live database connection, confirming
Railway env vars and connection pool are healthy.

**How to run:**
```bash
curl -s https://emissions-tracker-production.up.railway.app/ready | jq
```

**Pass criteria:** response body equals
```json
{"status": "ready", "database": "connected"}
```
and HTTP status is 200.

**Result:** TBD

---

## 4. Coverage freshness

**Verifies:** the materialized `coverage` snapshot is recent enough that public
consumers do not see stale data — last snapshot age must be under 24 hours.

**How to run:**
```bash
curl -s https://emissions-tracker-production.up.railway.app/v1/coverage/health | jq
```

**Pass criteria:**
- Response includes a `last_snapshot_at` (or equivalent) timestamp.
- Age of that timestamp is under 24 hours at time of check.
- HTTP status 200.

**Result:** TBD

---

## 5. Rate limit enforcement

**Verifies:** the per-IP rate limiter (nominal threshold: 100 req/min) actually
returns 429 responses when a single client goes over budget. Prevents a single
abusive caller from starving legit journalist traffic.

**How to run:**
```bash
# Fire 200 rapid requests from one IP and count status codes
for i in $(seq 1 200); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    https://emissions-tracker-production.up.railway.app/v1/coverage
done | sort | uniq -c
```

**Pass criteria:**
- At least one `429` appears in the distribution (rate limiter is engaged).
- The first ~100 requests succeed with `200` (limiter does not trip too early).
- No `5xx` responses.

**Result:** TBD

---

## Sign-off

Launch is approved only when every check above shows a concrete Result line
(not `TBD`) and every check is PASS. Record the runner name and timestamp next to
each Result when you fill it in.
