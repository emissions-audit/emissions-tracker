# Emissions Tracker

> *Cross-validated US corporate emissions — independent, free, after the EPA's exit*

An open API that aggregates corporate emissions data across EPA GHGRP, Climate TRACE, EU ETS, CDP, and SEC disclosures, then cross-validates self-reported figures against independent satellite and regulatory sources. Tracks 50+ companies across energy, utilities, materials, chemicals, mining, and transportation — covering the largest US corporate emitters. With the EPA terminating GHGRP reporting, this fills the vacuum with free, verifiable emissions data so journalists and researchers can hold companies accountable.

```bash
curl https://emissions-tracker-production.up.railway.app/v1/emissions?ticker=XOM
```

See it live: [`https://emissions-tracker-production.up.railway.app`](https://emissions-tracker-production.up.railway.app)

## Try it

```bash
# Coverage — which companies and years are tracked
curl https://emissions-tracker-production.up.railway.app/v1/stats

# Pull every source for a single company
curl "https://emissions-tracker-production.up.railway.app/v1/emissions?ticker=XOM&year=2023"

# Interactive HTML quickstart (no tools required)
open https://emissions-tracker-production.up.railway.app/quickstart

# Top emissions discrepancies — where reports disagree with measurements
curl "https://emissions-tracker-production.up.railway.app/v1/discrepancies/top?limit=5"
```

## See the cross-validation

Exxon reports **124.8 Mt CO2e** to EPA GHGRP; Climate TRACE satellites measure **168.4 Mt CO2e** — a **35% gap**.

<!-- TODO: replace code block with PNG screenshot once a human runs the live query -->
```text
XOM — 2023 Scope 1 emissions
EPA GHGRP (self-reported, US facilities)   124.8 Mt CO2e
Climate TRACE v6 (satellite, global owned) 168.4 Mt CO2e
Delta                                      +43.6 Mt  (+35.0%)
```

Full write-up: [`examples/discrepancy-exxon.md`](examples/discrepancy-exxon.md)

## Discrepancy Explorer

The [Discrepancy Explorer](https://emissions-tracker-production.up.railway.app/discrepancies) surfaces the biggest gaps between what companies report and what independent sources measure — ranked by severity.

```bash
# Browse the top discrepancies (HTML)
open https://emissions-tracker-production.up.railway.app/discrepancies

# Get discrepancies as JSON (filterable, sortable)
curl "https://emissions-tracker-production.up.railway.app/v1/discrepancies?sort=delta&limit=10"

# Download as CSV (for spreadsheets and data journalism)
curl -O https://emissions-tracker-production.up.railway.app/v1/discrepancies.csv
```

Filter by `ticker`, `company`, `year`, `sector`, `min_delta`. Sort by `spread_pct` (default), `delta`, or `ticker`.

## Quick Start

```bash
# Clone and start
git clone https://github.com/emissions-audit/emissions-tracker.git
cd emissions-tracker
cp .env.example .env
docker compose up db -d

# Install
pip install -e ".[dev]"

# Seed companies and ingest data
emissions-pipeline seed
emissions-pipeline ingest edgar --years 2022,2023,2024
emissions-pipeline ingest climate_trace --years 2022,2023,2024
emissions-pipeline validate

# Start the API
uvicorn src.api.main:app --reload
```

API docs at http://localhost:8000/docs

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /v1/companies` | List tracked companies |
| `GET /v1/emissions` | Cross-company emissions query |
| `GET /v1/emissions/compare` | Side-by-side comparison |
| `GET /v1/discrepancies` | Cross-validation flags |
| `GET /v1/discrepancies/top` | Biggest discrepancies |
| `GET /v1/pledges/tracker` | Net-zero pledge vs reality |
| `GET /v1/stats` | Database statistics |
| `GET /v1/meta/sectors` | Available sectors |
| `GET /v1/meta/methodology` | Data methodology docs |
| `GET /v1/export/full` | Bulk export (Pro tier) |
| `GET /v1/project-stats` | GitHub stars, forks, contributors |
| `GET /v1/analytics/summary` | API usage analytics |
| `GET /landing` | Landing page with live stats |
| `GET /pricing` | Pricing tiers (Free/Pro/Enterprise) |
| `GET /enterprise` | Enterprise inquiry form |

Full API docs: http://localhost:8000/docs

## Data Sources

| # | Source | Type | Coverage | Status |
|---|---|---|---|---|
| 1 | **SEC EDGAR** (XBRL) | Regulatory | US public company filings | Active |
| 2 | **Climate TRACE** v6 | Satellite | 350M+ global assets, 50+ tracked companies | Active |
| 3 | **EPA GHGRP** | Regulatory | ~8K US facilities (Scope 1) | Active |
| 4 | **EU ETS** | Regulatory | ~10K EU/EEA installations (Scope 1) | Active |
| 5 | **CDP** | Voluntary | Corporate climate disclosures | Active (sample data) |
| 6 | **CARB SB253** | Regulatory | California corporate emissions | Pending (reporting starts 2026-07) |

## Tech Stack

- Python 3.12, FastAPI, Typer CLI
- SQLAlchemy 2.0, PostgreSQL 16, Alembic
- httpx, pdfplumber, Anthropic SDK
- Docker Compose

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Deployment

### Railway (recommended)

1. Create a [Railway](https://railway.app) account
2. New Project → Deploy from GitHub repo
3. Railway auto-detects `Dockerfile.api` via `railway.json`
4. Add a PostgreSQL service from the Railway dashboard
5. Railway auto-sets `DATABASE_URL` — no manual config needed
6. Set `ANTHROPIC_API_KEY` in the service variables (optional — only needed for PDF extraction)
7. After deploy, run migrations:
   ```bash
   railway run alembic upgrade head
   railway run emissions-pipeline seed
   ```

### Docker Compose (self-hosted)

```bash
git clone https://github.com/emissions-audit/emissions-tracker.git
cd emissions-tracker
cp .env.example .env  # edit DATABASE_URL and ANTHROPIC_API_KEY
docker compose up -d
# Run migrations
docker compose exec api alembic upgrade head
docker compose exec api emissions-pipeline seed
```

### Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe — returns `{"status": "healthy"}` |
| `GET /ready` | Readiness probe — checks database connectivity |

## License

MIT
