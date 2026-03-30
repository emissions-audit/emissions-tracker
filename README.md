# Emissions Tracker

Open-source corporate emissions transparency tracker. Aggregates public emissions disclosures into a free, searchable database with a REST API.

## Why

~100 companies produce ~71% of global emissions. The data exists but is scattered across paywalled databases costing $25K-$200K/year. This project makes it free, open, and developer-friendly.

## Key Feature: Cross-Validation

We compare emissions data across multiple independent sources (SEC filings, satellite measurements, voluntary disclosures) and flag discrepancies. When Shell says X but satellites say Y, you'll see it.

## Quick Start

```bash
# Clone and start
git clone https://github.com/cphalpert/emissions-tracker.git
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

Full API docs: http://localhost:8000/docs

## Data Sources

1. **SEC EDGAR** (XBRL) -- US regulatory filings
2. **Climate TRACE** -- Satellite-derived emissions
3. **CDP** -- Voluntary corporate disclosures
4. **Sustainability Reports** -- LLM-extracted from PDFs

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
git clone https://github.com/cphalpert/emissions-tracker.git
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
