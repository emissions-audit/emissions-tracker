#!/bin/bash
# launch-stress-test.sh — ET-50 launch-readiness stress test
#
# Verifies the production Railway instance absorbs journalist-spike traffic
# (~100 req/s sustained for 60s) without 5xx errors.
#
# Usage:
#   scripts/launch-stress-test.sh [base_url]
#
# Example:
#   scripts/launch-stress-test.sh
#   scripts/launch-stress-test.sh https://staging.example.com
#
# Exit codes:
#   0  — both endpoints returned zero 5xx responses
#   1  — one or more 5xx responses observed, or tooling failure
#
# Notes:
#   - Prefers `hey` (github.com/rakyll/hey). Falls back to parallel curl + xargs.
#   - Designed to run under Git Bash on Windows — uses /tmp/ paths only.
#   - Make executable with: chmod +x scripts/launch-stress-test.sh

set -uo pipefail

BASE_URL="${1:-https://emissions-tracker-production.up.railway.app}"
DURATION_SECS=60
RATE_PER_ENDPOINT=50   # 50 + 50 = ~100 req/s combined
CONCURRENCY=10

EMISSIONS_URL="${BASE_URL}/v1/emissions?ticker=XOM"
COVERAGE_URL="${BASE_URL}/v1/coverage"

EMISSIONS_OUT="/tmp/stress-emissions.txt"
COVERAGE_OUT="/tmp/stress-coverage.txt"

echo "========================================="
echo "ET-50 Launch Stress Test"
echo "========================================="
echo "Target URL     : ${BASE_URL}"
echo "Duration       : ${DURATION_SECS}s"
echo "Rate/endpoint  : ${RATE_PER_ENDPOINT} req/s"
echo "Concurrency    : ${CONCURRENCY}"
echo "Combined rate  : ~$((RATE_PER_ENDPOINT * 2)) req/s"
echo "Start time     : $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# ---------------------------------------------------------------------------
# Tool detection
# ---------------------------------------------------------------------------
USE_HEY=0
if command -v hey >/dev/null 2>&1; then
    USE_HEY=1
    echo "Using: hey ($(command -v hey))"
elif command -v curl >/dev/null 2>&1 && command -v xargs >/dev/null 2>&1; then
    USE_HEY=0
    echo "Using: curl + xargs fallback (hey not found)"
else
    echo "ERROR: neither 'hey' nor 'curl'+'xargs' available."
    echo "Install hey (https://github.com/rakyll/hey) or ensure curl+xargs are on PATH."
    exit 1
fi
echo ""

# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------
run_hey() {
    local url="$1"
    local out="$2"
    hey -z "${DURATION_SECS}s" -q "${RATE_PER_ENDPOINT}" -c "${CONCURRENCY}" "${url}" > "${out}" 2>&1
}

run_curl_fallback() {
    # Parallel curl loop: spawn CONCURRENCY workers that each curl in a loop
    # for DURATION_SECS seconds. Each curl writes "status time_total" to the
    # output file. No per-request rate limiting — we rely on concurrency +
    # network latency to hit roughly the target rate.
    local url="$1"
    local out="$2"
    : > "${out}"

    local end_ts
    end_ts=$(( $(date +%s) + DURATION_SECS ))

    worker() {
        local u="$1"
        local o="$2"
        local end="$3"
        while [ "$(date +%s)" -lt "${end}" ]; do
            curl -s -o /dev/null \
                 -w "%{http_code} %{time_total}\n" \
                 --max-time 10 \
                 "${u}" >> "${o}" 2>/dev/null || echo "000 0" >> "${o}"
        done
    }

    export -f worker
    seq 1 "${CONCURRENCY}" | xargs -P "${CONCURRENCY}" -I{} \
        bash -c "worker '${url}' '${out}' '${end_ts}'"
}

# ---------------------------------------------------------------------------
# Summarizers
# ---------------------------------------------------------------------------
summarize_hey() {
    local label="$1"
    local out="$2"

    local total success five_xx p50 p95 p99
    total=$(grep -E "Total:" "${out}" | head -1 | awk '{print $2}')
    # hey prints "[200] N responses" lines — sum 2xx as success.
    success=$(grep -oE "\[2[0-9]{2}\][[:space:]]+[0-9]+" "${out}" \
              | awk '{s += $2} END {print s+0}')
    five_xx=$(grep -oE "\[5[0-9]{2}\][[:space:]]+[0-9]+" "${out}" \
              | awk '{s += $2} END {print s+0}')
    p50=$(grep -E "^[[:space:]]*50% in" "${out}" | awk '{print $3}')
    p95=$(grep -E "^[[:space:]]*95% in" "${out}" | awk '{print $3}')
    p99=$(grep -E "^[[:space:]]*99% in" "${out}" | awk '{print $3}')

    local total_num
    total_num=$(grep -oE "\[[0-9]{3}\][[:space:]]+[0-9]+" "${out}" \
                | awk '{s += $2} END {print s+0}')
    [ -z "${total_num}" ] && total_num=0
    [ -z "${success}" ]   && success=0
    [ -z "${five_xx}" ]   && five_xx=0

    local rate="n/a"
    if [ "${total_num}" -gt 0 ]; then
        rate=$(awk -v s="${success}" -v t="${total_num}" 'BEGIN {printf "%.2f%%", (s/t)*100}')
    fi

    echo "--- ${label} ---"
    echo "  Requests  : ${total_num}"
    echo "  2xx       : ${success} (${rate})"
    echo "  5xx       : ${five_xx}"
    echo "  p50       : ${p50:-n/a}"
    echo "  p95       : ${p95:-n/a}"
    echo "  p99       : ${p99:-n/a}"
    echo ""

    FIVE_XX_TOTAL=$((FIVE_XX_TOTAL + five_xx))
    REQ_TOTAL=$((REQ_TOTAL + total_num))
}

summarize_curl() {
    local label="$1"
    local out="$2"

    # Each line: "<status> <time_total>"
    local total success five_xx
    total=$(wc -l < "${out}" | tr -d ' ')
    success=$(awk '$1 ~ /^2[0-9][0-9]$/ {c++} END {print c+0}' "${out}")
    five_xx=$(awk '$1 ~ /^5[0-9][0-9]$/ {c++} END {print c+0}' "${out}")

    # Percentiles on time_total (seconds, float)
    local p50 p95 p99
    read -r p50 p95 p99 < <(
        awk '{print $2}' "${out}" \
        | sort -n \
        | awk '
            {a[NR]=$1}
            END {
                if (NR == 0) { print "n/a n/a n/a"; exit }
                i50 = int(NR*0.50); if (i50 < 1) i50 = 1
                i95 = int(NR*0.95); if (i95 < 1) i95 = 1
                i99 = int(NR*0.99); if (i99 < 1) i99 = 1
                printf "%.4fs %.4fs %.4fs\n", a[i50], a[i95], a[i99]
            }'
    )

    [ -z "${total}" ]   && total=0
    [ -z "${success}" ] && success=0
    [ -z "${five_xx}" ] && five_xx=0

    local rate="n/a"
    if [ "${total}" -gt 0 ]; then
        rate=$(awk -v s="${success}" -v t="${total}" 'BEGIN {printf "%.2f%%", (s/t)*100}')
    fi

    echo "--- ${label} ---"
    echo "  Requests  : ${total}"
    echo "  2xx       : ${success} (${rate})"
    echo "  5xx       : ${five_xx}"
    echo "  p50       : ${p50:-n/a}"
    echo "  p95       : ${p95:-n/a}"
    echo "  p99       : ${p99:-n/a}"
    echo ""

    FIVE_XX_TOTAL=$((FIVE_XX_TOTAL + five_xx))
    REQ_TOTAL=$((REQ_TOTAL + total))
}

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
FIVE_XX_TOTAL=0
REQ_TOTAL=0

echo ">>> Hitting /v1/emissions and /v1/coverage in parallel..."
if [ "${USE_HEY}" -eq 1 ]; then
    run_hey "${EMISSIONS_URL}" "${EMISSIONS_OUT}" &
    EMISSIONS_PID=$!
    run_hey "${COVERAGE_URL}"  "${COVERAGE_OUT}" &
    COVERAGE_PID=$!
    wait "${EMISSIONS_PID}"
    wait "${COVERAGE_PID}"
else
    run_curl_fallback "${EMISSIONS_URL}" "${EMISSIONS_OUT}" &
    EMISSIONS_PID=$!
    run_curl_fallback "${COVERAGE_URL}"  "${COVERAGE_OUT}" &
    COVERAGE_PID=$!
    wait "${EMISSIONS_PID}"
    wait "${COVERAGE_PID}"
fi

echo ""
echo "========================================="
echo "Results"
echo "========================================="
echo "End time       : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ "${USE_HEY}" -eq 1 ]; then
    summarize_hey "GET /v1/emissions?ticker=XOM" "${EMISSIONS_OUT}"
    summarize_hey "GET /v1/coverage"             "${COVERAGE_OUT}"
else
    summarize_curl "GET /v1/emissions?ticker=XOM" "${EMISSIONS_OUT}"
    summarize_curl "GET /v1/coverage"             "${COVERAGE_OUT}"
fi

echo "========================================="
if [ "${FIVE_XX_TOTAL}" -eq 0 ]; then
    echo "PASS: 0 5xx errors across ${REQ_TOTAL} requests"
    echo "========================================="
    exit 0
else
    echo "FAIL: ${FIVE_XX_TOTAL} 5xx errors across ${REQ_TOTAL} requests"
    echo "========================================="
    exit 1
fi
