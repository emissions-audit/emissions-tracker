from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc as sa_desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import CrossValidation, Company


def build_router(get_db) -> APIRouter:
    r = APIRouter(tags=["pages"])

    @r.get("/discrepancies", response_class=HTMLResponse)
    async def discrepancies_page(db: AsyncSession = get_db):
        stmt = (
            select(CrossValidation, Company.name, Company.ticker)
            .join(Company, CrossValidation.company_id == Company.id)
            .where(CrossValidation.flag.in_(["yellow", "red"]))
            .order_by(sa_desc(CrossValidation.spread_pct))
            .limit(20)
        )
        rows = (await db.execute(stmt)).all()

        table_rows = ""
        for cv, name, ticker in rows:
            delta = float(cv.max_value - cv.min_value)
            delta_fmt = f"{delta / 1_000_000:,.1f}"
            spread_fmt = f"{float(cv.spread_pct):,.1f}"
            min_fmt = f"{float(cv.min_value) / 1_000_000:,.1f}"
            max_fmt = f"{float(cv.max_value) / 1_000_000:,.1f}"
            flag_icon = "\U0001f534" if cv.flag == "red" else "\U0001f7e1"
            table_rows += (
                f"<tr>"
                f"<td>{flag_icon}</td>"
                f"<td><a href=\"/v1/companies/{cv.company_id}/validation\">{name}</a></td>"
                f"<td><code>{ticker or chr(8212)}</code></td>"
                f"<td>{cv.year}</td>"
                f"<td>Scope {cv.scope}</td>"
                f"<td>{min_fmt}</td>"
                f"<td>{max_fmt}</td>"
                f"<td><strong>+{delta_fmt} Mt</strong></td>"
                f"<td>{spread_fmt}%</td>"
                f"<td>{cv.source_count}</td>"
                f"</tr>\n"
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Discrepancy Explorer &mdash; Emissions Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #222; line-height: 1.5; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .pitch {{ color: #555; margin-top: 0; font-size: 1.05rem; }}
  h2 {{ margin-top: 2rem; font-size: 1.2rem; border-bottom: 1px solid #eee; padding-bottom: 0.25rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #eee; vertical-align: top; }}
  th {{ background: #fafafa; position: sticky; top: 0; }}
  td code {{ background: #f5f5f5; padding: 1px 4px; border-radius: 3px; }}
  a {{ color: #0366d6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .actions {{ margin-top: 1.5rem; font-size: 0.95rem; }}
  .actions a {{ margin-right: 1.5rem; }}
  footer {{ margin-top: 2.5rem; color: #777; font-size: 0.9rem; text-align: center; }}
</style>
</head>
<body>
<h1>Discrepancy Explorer</h1>
<p class="pitch">We cross-validate what companies report against what satellites and regulators measure.
These are the biggest gaps.</p>

<div class="actions">
  <a href="/v1/discrepancies.csv">Download CSV</a>
  <a href="/v1/discrepancies?limit=100">JSON API</a>
  <a href="/quickstart">API Quickstart</a>
</div>

<h2>Top Discrepancies</h2>
<table>
<thead>
<tr>
  <th></th><th>Company</th><th>Ticker</th><th>Year</th><th>Scope</th>
  <th>Low (Mt)</th><th>High (Mt)</th><th>Delta</th><th>Gap</th><th>Sources</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>

<footer>
  Data from EPA GHGRP, Climate TRACE, EU ETS, CDP, SEC filings.
  <a href="https://github.com/emissions-audit/emissions-tracker">Open source</a> &middot;
  <a href="/quickstart">API docs</a>
</footer>
</body>
</html>"""
        return HTMLResponse(html)

    return r
