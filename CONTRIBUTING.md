# Contributing to Emissions Tracker

Thank you for your interest in contributing to the Emissions Tracker project. Whether you're fixing a bug, adding a new data source, submitting emissions data, or improving documentation, your help makes corporate emissions data more transparent and accessible.

This project is MIT licensed. By contributing, you agree that your contributions will be licensed under the same terms.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style and Linting](#code-style-and-linting)
- [Adding a New Data Source](#adding-a-new-data-source)
- [Submitting Emissions Data](#submitting-emissions-data)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Issue Guidelines](#issue-guidelines)

---

## Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for PostgreSQL 16)
- Git

### Steps

1. **Clone the repository:**

   ```bash
   git clone https://github.com/emissions-audit/emissions-tracker.git
   cd emissions-tracker
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

3. **Install the package in editable mode with dev dependencies:**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Start PostgreSQL with Docker Compose:**

   ```bash
   docker compose up -d
   ```

5. **Run database migrations:**

   ```bash
   alembic upgrade head
   ```

6. **Seed initial data and verify everything works:**

   ```bash
   emissions-pipeline seed
   emissions-pipeline ingest edgar --years 2023
   ```

7. **Start the API server (optional, for API work):**

   ```bash
   uvicorn src.api.main:app --reload
   ```

---

## Running Tests

Run the full test suite with:

```bash
pytest tests/ -v
```

Tests use an async SQLite backend by default so you do not need PostgreSQL running for most tests. If you add a new feature or fix a bug, include tests covering the change.

To run a specific test file or test:

```bash
pytest tests/pipeline/test_sources.py -v
pytest tests/api/ -v -k "test_company_list"
```

---

## Code Style and Linting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. The configuration in `pyproject.toml` specifies:

- **Target version:** Python 3.12
- **Line length:** 100 characters

Before submitting a PR, run:

```bash
ruff check .          # Lint
ruff format .         # Format
ruff check . --fix    # Auto-fix lint issues where possible
```

General style expectations:

- Use type hints for all function signatures.
- Prefer `async`/`await` for I/O-bound operations.
- Use `dataclass` or Pydantic models for structured data.
- Keep functions focused and reasonably short.

---

## Adding a New Data Source

The pipeline uses a `BaseSource` abstract class to normalize data ingestion from different providers. To add a new source:

### 1. Create a new source module

Add a file in `src/pipeline/sources/` (e.g., `my_source.py`).

### 2. Subclass `BaseSource`

Implement the required `fetch_emissions` method and optionally `fetch_pledges`:

```python
from src.pipeline.sources.base import BaseSource, RawEmission, RawPledge


class MySource(BaseSource):
    name = "my_source"

    async def fetch_emissions(
        self, tickers: list[str], years: list[int]
    ) -> list[RawEmission]:
        # Fetch and parse data from your source.
        # Return a list of RawEmission dataclass instances.
        results = []
        # ... your extraction logic ...
        return results

    async def fetch_pledges(self, tickers: list[str]) -> list[RawPledge]:
        # Optional: return pledge/target data if the source provides it.
        return []
```

### 3. Key points

- **`RawEmission` fields:** `company_ticker`, `year`, `scope` (e.g., `"Scope 1"`), `value`, `unit` (e.g., `"t_co2e"` or `"mt_co2e"`), `methodology`, `verified`, `source_url`, `filing_type`, `parser_used`.
- **`RawPledge` fields:** `company_ticker`, `pledge_type`, `target_year`, `target_scope`, `target_reduction_pct`, `baseline_year`, `baseline_value`, `source_url`.
- Use `httpx.AsyncClient` for HTTP requests (consistent with existing sources).
- Handle API errors gracefully -- skip records that fail rather than crashing the entire pipeline.
- Set `source_url` so data can be traced back to its origin.

### 4. Register the source

Add the source to `src/pipeline/sources/__init__.py` so the CLI can discover it.

### 5. Write tests

Add tests in `tests/pipeline/` that mock HTTP responses and verify your parsing logic returns correct `RawEmission` objects.

For reference, look at `src/pipeline/sources/edgar.py` (XBRL parsing) or `src/pipeline/sources/climate_trace.py` (API-based) as examples.

---

## Submitting Emissions Data

Community data contributions are valuable. If you have emissions data for companies not yet covered (or corrections to existing data), you can submit it without writing code.

### Data format

Prepare your data as **JSON** or **CSV** with the following fields:

**Emissions (required fields):**

| Field | Type | Example |
|---|---|---|
| `company_ticker` | string | `"AAPL"` |
| `year` | integer | `2023` |
| `scope` | string | `"Scope 1"`, `"Scope 2"`, `"Scope 3"`, or `"Total"` |
| `value` | float | `125000.0` |
| `unit` | string | `"t_co2e"` or `"mt_co2e"` |

**Optional fields:** `methodology`, `verified` (boolean), `source_url`

### How to submit

1. **Open a GitHub Issue** titled `data: <company ticker> <year>` (e.g., `data: AAPL 2023`).
2. Attach your JSON or CSV file, or paste the data directly in the issue.
3. Include the **source URL** or citation for every data point. Unsourced data cannot be accepted.
4. Describe whether this is **new data** or a **correction** to existing records.

> A structured "Challenge a Number" issue template is coming with the community corrections launch. Until then, free-form issues work fine.

**Example JSON:**

```json
[
  {
    "company_ticker": "AAPL",
    "year": 2023,
    "scope": "Scope 1",
    "value": 52200.0,
    "unit": "t_co2e",
    "source_url": "https://apple.com/environment/pdf/Apple_Environmental_Progress_Report_2024.pdf"
  }
]
```

Maintainers will validate and ingest submitted data through the pipeline's validation step (`emissions-pipeline validate`).

---

## Pull Request Guidelines

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
feat(sources): add EPA GHGRP data source
fix(api): correct scope aggregation for multi-year queries
docs: update setup instructions for Docker Compose v2
test(pipeline): add validation edge cases for negative values
data: add 2023 emissions for AAPL, MSFT, GOOG
```

Common prefixes: `feat`, `fix`, `docs`, `test`, `refactor`, `data`, `chore`.

### PR expectations

- **Keep PRs small and focused.** One feature, one bug fix, or one data source per PR.
- **Include tests** for any new functionality or bug fix.
- **Run `ruff check .` and `ruff format .`** before pushing -- CI will reject unformatted code.
- **Run `pytest tests/ -v`** locally and confirm tests pass.
- **Update documentation** if your change affects setup steps, CLI usage, or API endpoints.
- **Fill out the PR description** explaining what changed and why.

### Review process

- A maintainer will review your PR, usually within a few days.
- Address review feedback by pushing new commits (do not force-push during review).
- Once approved, a maintainer will merge your PR.

---

## Issue Guidelines

When opening an issue, please include the relevant details below. Structured issue templates will be added soon; for now, free-form issues with these fields work fine.

### Bug Report

- **Title:** Clear, specific summary (e.g., "CDP source returns duplicate Scope 2 values for CVX 2022")
- **Steps to reproduce:** Commands run, API endpoints called, or data queried
- **Expected behavior:** What you expected to happen
- **Actual behavior:** What happened instead, including error messages or incorrect values
- **Environment:** Python version, OS, Docker version if relevant

### Feature Request

- **Title:** Brief description of the proposed feature
- **Motivation:** What problem does this solve? Who benefits?
- **Proposed solution:** How you envision it working (API design, CLI flags, etc.)
- **Alternatives considered:** Other approaches you thought about

### Data Correction / Addition

- **Company ticker and year(s)** affected
- **Current value** (if correcting) and **proposed value**
- **Source URL** with the authoritative data
- Attach a JSON/CSV file for bulk submissions

---

## Questions?

If you're unsure about anything, open a Discussion or file an issue. We're happy to help first-time contributors find a good starting point.
