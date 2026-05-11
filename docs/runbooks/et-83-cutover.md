# ET-83 Production Cutover Runbook

Apply the unit-standardization migration (`value_mt_co2e` → `value_t_co2e`) to Railway prod, truncate the broken-unit ingest data, re-ingest with the corrected adapters, and verify per-source magnitudes.

**Branch shipped:** `et-83-unit-standardization` (6 commits, 0 failed / 227 passed / 11 skipped at HEAD `3dea551`).
**Plan:** `1 Projects/emissions-tracker/artifacts/plans/plan-2026-04-27-unit-standardization.md` Phase 6.
**Pre-requisite:** ACT-20 should ideally be done first — verify `alembic upgrade head` + downgrade idempotency against a local Postgres before touching production. If skipping ACT-20, accept higher rollback risk and confirm Step 2 of Task 1 below carefully.

Mark unknown operational details as `{{CONFIRM: ...}}` and verify before acting.

---

## 1. Pre-cutover verification

1. **Approve PR + merge to `main`.**
   - Code-review the full diff (~30 files across the 6 commits).
   - Squash or merge — the per-phase commit history is useful for review but not required to preserve in `main`.
   - Railway auto-deploys on merge.

2. **Take a manual Railway Postgres snapshot.**
   - In Railway dashboard → Postgres service → Backups → "Take snapshot".
   - Note the snapshot ID. This is the rollback anchor for Section 4.

3. **(Optional) Staging dry-run.**
   - `{{CONFIRM: does a staging environment exist?}}` If yes:
     - Deploy the merged branch to staging.
     - `railway run alembic upgrade head` against staging DB.
     - Trigger ingest workflow against staging.
     - `curl https://{{STAGING_URL}}/v1/discrepancies?ticker=XOM | jq` — verify CDP/CARB return 100M-150M tonnes.
   - If no staging, skip and proceed cautiously to Section 2.

---

## 2. Production migration + truncate + re-ingest

> **Abort criteria:** Any step that exits non-zero or returns unexpected output → STOP and follow rollback (Section 4) before doing anything else.

1. **Wait for Railway deploy to complete.**
   - Railway dashboard → API service → Deployments → confirm latest commit `3dea551` (or the merge commit on `main`) is "Active".

2. **Apply the alembic migration.**
   ```bash
   railway run alembic upgrade head
   ```
   Expected: `Running upgrade ... -> a27e000535e7, rename value_mt_co2e to value_t_co2e` and exit 0.

   Verify schema:
   ```bash
   railway run psql -c "\d emissions" | grep value_t_co2e
   railway run psql -c "\d source_entries" | grep value_t_co2e
   railway run psql -c "\d pledges" | grep baseline_value_t_co2e
   ```
   Expected: all three return matches. If any is missing, abort.

3. **Truncate broken-unit data.**
   ```bash
   railway run psql -c "TRUNCATE source_entries, emissions, cross_validations, filings RESTART IDENTITY CASCADE;"
   ```
   Expected: all four tables emptied. `companies` and `pledges` are untouched (so company list + net-zero pledges survive).

4. **Re-trigger the ingest workflow.**
   ```bash
   gh workflow run ingest.yml --repo emissions-audit/emissions-tracker
   gh run watch
   ```
   Expected: ~3-5 min runtime. Look in the logs for the sanity validator output:
   ```
   Upserted N emissions records
   ```
   No `❌ SANITY CHECK FAILED` message. If sanity check fails, abort (a value > 10 Gt is a sign the unit fix didn't propagate cleanly).

5. **Run validate to recompute cross-validations.**
   - The ingest workflow may already invoke validate. If not:
     ```bash
     railway run emissions-pipeline validate
     ```

6. **Spot-check `/v1/discrepancies?ticker=XOM`.**
   ```bash
   curl -s "https://emissions-tracker-production.up.railway.app/v1/discrepancies?ticker=XOM" | jq
   ```
   Verify per-source magnitude ranges:

   | Source | Acceptable XOM Scope 1 range |
   |---|---|
   | CDP | 100M – 150M tonnes (2023) |
   | CARB | 100M – 150M tonnes (2026) |
   | Climate TRACE | 50M – 500M tonnes (wide — asset-rollup limitation, ET-84) |
   | EU ETS | 1M – 30M tonnes (EU operations only — ET-85) |
   | EPA GHGRP | 30M – 100M tonnes (US facilities only — ET-85) |

   **If CDP or CARB is outside 100M-150M, ABORT.** Investigate before continuing — this means the unit fix didn't land cleanly.

7. **Verify `/v1/stats`.**
   ```bash
   curl -s "https://emissions-tracker-production.up.railway.app/v1/stats" | jq
   ```
   Expected: `company_count: 52`, `filing_count: ~280`, `emission_count: ~290` (similar to pre-migration baseline). Significant deviation → investigate.

8. **Update backlog status.**
   - Mark **ET-83** as `✅ Done` in `1 Projects/emissions-tracker/artifacts/tasks/backlog.md`.
   - Mark **ACT-20** as `✅ Done` (cutover verified the migration applies cleanly to real Postgres — supersedes the local-roundtrip check).
   - Add a session log entry under `1 Projects/emissions-tracker/sessions/YYYY-MM-DD.md` summarizing cutover outcome + per-source magnitudes observed.

---

## 3. Post-cutover follow-up

1. **Re-evaluate ET-84 priority.**
   - If Climate TRACE values for any anchor ticker (XOM/CVX/SHEL) are >10× CDP, bump ET-84 to P0.
   - Otherwise leave at P1.

2. **Update ACT-13 placeholder fills.**
   - `/v1/discrepancies` now returns clean tonne-magnitude data.
   - Placeholders in `outputs/launch/2026-04-26-act13-suggested-copy.md` (`{{EXXON_REPORTED_T_CO2E}}` etc.) can be filled with real values.
   - Update launch content drafts: `show-hn.md`, `exxon-discrepancy.md`, `shell-discrepancy.md`, `chevron-discrepancy.md`, `pitch-template.md`.

3. **Schedule next CSO refresh.**
   - Per session log recommendation, run `/cso emissions-tracker` after re-ingest succeeds, before resuming ACT-10 journalist outreach planning.

---

## 4. Rollback path (if any Section 2 step fails irrecoverably)

1. **Restore Railway snapshot from Section 1 Step 2.**
   - `{{CONFIRM: Railway snapshot restore syntax}}` — typically dashboard → Postgres → Backups → restore.

2. **Revert the schema rename.**
   ```bash
   railway run alembic downgrade -1
   ```
   This re-renames columns back to `value_mt_co2e` and `baseline_value_mt_co2e`.

3. **Redeploy the previous git commit.**
   - In Railway: API service → Deployments → previous active deployment → "Redeploy".
   - OR: `git -C ...emissions-tracker push origin <prev-sha>:main --force-with-lease` from a local clone (only if Railway redeploy can't roll back the API code separately from DB).

4. **Verify service is operational** at the previous (pre-migration) state.
   - Mixed-unit data is back, but the API doesn't crash. CV flags will be wrong as before — this is the known pre-fix state, not a new failure.

5. **Triage what went wrong.**
   - Open a follow-up issue. Don't re-attempt cutover until the root cause is understood.

---

## Notes

- **Why truncate, not migrate values:** The pre-fix data was a mix of tonnes (CDP/CARB) and megatonnes (Climate TRACE/EU ETS/EPA — 1000× too small). No reliable way to distinguish which rows had which scaling without re-ingesting. Truncate + re-ingest is the safe path.
- **Companies + pledges preserved:** `TRUNCATE` excludes those tables. Pledge baselines were also column-renamed (`baseline_value_t_co2e`) but the values were already tonnes pre-migration, so they remain correct.
- **Sanity validator wired:** Phase 3 added `check_sanity()` which the re-ingest will run. If any company-year exceeds 10 Gt CO2e, ingest fails fast (`typer.Exit(2)`).
