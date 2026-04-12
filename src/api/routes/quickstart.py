from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


_QUICKSTART_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emissions Tracker API \u2014 Quickstart</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         max-width: 820px; margin: 2rem auto; padding: 0 1rem; color: #222; line-height: 1.5; }
  h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
  .pitch { color: #555; margin-top: 0; font-size: 1.05rem; }
  h2 { margin-top: 2rem; font-size: 1.2rem; border-bottom: 1px solid #eee; padding-bottom: 0.25rem; }
  pre { background: #f5f5f5; border: 1px solid #e5e5e5; padding: 0.75rem; overflow-x: auto;
        border-radius: 4px; font-size: 0.9rem; }
  code { font-family: "SFMono-Regular", Menlo, Consolas, monospace; }
  table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; font-size: 0.95rem; }
  th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; vertical-align: top; }
  th { background: #fafafa; }
  td code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; }
  footer { margin-top: 2.5rem; color: #777; font-size: 0.9rem; text-align: center; }
  a { color: #0366d6; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>

<h1>Emissions Tracker API \u2014 Quickstart</h1>
<p class="pitch">Cross-validated US corporate emissions data. Free, open, no signup.</p>

<h2>Try it</h2>
<p>Fetch Exxon's emissions with a single HTTP call:</p>
<pre><code>curl https://api.emissions-audit.org/v1/emissions?ticker=XOM</code></pre>
<p>If the endpoint requires authentication, add an API key header:
<code>-H "X-API-Key: demo"</code></p>

<h2>Endpoints</h2>
<table>
  <thead>
    <tr><th>Method &amp; Path</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><code>GET /</code></td><td>API info (JSON)</td></tr>
    <tr><td><code>GET /health</code></td><td>Liveness check</td></tr>
    <tr><td><code>GET /ready</code></td><td>Readiness check (database connectivity)</td></tr>
    <tr><td><code>GET /quickstart</code></td><td>This page</td></tr>
    <tr><td><code>GET /docs</code></td><td>Interactive OpenAPI / Swagger UI</td></tr>
    <tr><td><code>GET /v1/companies</code></td><td>List companies (filter by sector, country, subsector)</td></tr>
    <tr><td><code>GET /v1/companies/{company_id}</code></td><td>Fetch a single company</td></tr>
    <tr><td><code>GET /v1/companies/{company_id}/emissions</code></td><td>Emissions for one company</td></tr>
    <tr><td><code>GET /v1/companies/{company_id}/filings</code></td><td>Filings for one company</td></tr>
    <tr><td><code>GET /v1/companies/{company_id}/validation</code></td><td>Cross-validation records for one company</td></tr>
    <tr><td><code>GET /v1/companies/{company_id}/pledges</code></td><td>Climate pledges for one company</td></tr>
    <tr><td><code>GET /v1/emissions</code></td><td>Query emissions (supports <code>ticker</code>, <code>year</code>, <code>scope</code>, pagination)</td></tr>
    <tr><td><code>GET /v1/emissions/compare</code></td><td>Compare emissions across companies</td></tr>
    <tr><td><code>GET /v1/discrepancies</code></td><td>List cross-source discrepancies</td></tr>
    <tr><td><code>GET /v1/discrepancies/top</code></td><td>Top discrepancies by spread</td></tr>
    <tr><td><code>GET /v1/pledges/tracker</code></td><td>Pledge progress tracker</td></tr>
    <tr><td><code>GET /v1/coverage</code></td><td>Current coverage snapshot</td></tr>
    <tr><td><code>GET /v1/coverage/history</code></td><td>Historical coverage snapshots</td></tr>
    <tr><td><code>GET /v1/coverage/health</code></td><td>Coverage alert status</td></tr>
    <tr><td><code>GET /v1/stats</code></td><td>High-level counts (companies, emissions, year range)</td></tr>
    <tr><td><code>GET /v1/meta/sectors</code></td><td>List of sectors covered</td></tr>
    <tr><td><code>GET /v1/meta/methodology</code></td><td>Methodology &amp; source descriptions</td></tr>
    <tr><td><code>GET /v1/analytics/summary</code></td><td>API usage analytics summary</td></tr>
    <tr><td><code>GET /v1/metrics</code></td><td>Instance health metrics (uptime, coverage, database)</td></tr>
    <tr><td><code>GET /v1/export/full</code></td><td>Full dataset export</td></tr>
    <tr><td><code>GET /v1/export/companies/{company_id}</code></td><td>Per-company export</td></tr>
  </tbody>
</table>

<h2>Authentication</h2>
<p>Pass your API key in the <code>X-API-Key</code> header on each request:</p>
<pre><code>curl -H "X-API-Key: your-key-here" https://api.emissions-audit.org/v1/emissions?ticker=XOM</code></pre>
<p>Need a key? Open an issue on
<a href="https://github.com/emissions-audit/emissions-tracker">GitHub</a> and we'll hand one out.</p>

<h2>Rate limits</h2>
<p>100 requests per minute by default. Higher limits available on request for research use.</p>

<footer>
  <a href="https://github.com/emissions-audit/emissions-tracker">github.com/emissions-audit/emissions-tracker</a>
</footer>

</body>
</html>
"""


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["quickstart"])

    @router.get("/quickstart", response_class=HTMLResponse)
    def quickstart() -> HTMLResponse:
        return HTMLResponse(content=_QUICKSTART_HTML, status_code=200)

    return router
