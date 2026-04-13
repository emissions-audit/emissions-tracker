from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


_PRICING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pricing &mdash; Emissions Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         color: #222; line-height: 1.6; }
  .header { text-align: center; padding: 2.5rem 1rem 1.5rem; }
  .header h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
  .header p { color: #555; font-size: 1.05rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 1.5rem; max-width: 960px; margin: 0 auto; padding: 0 1rem 2rem; }
  .card { border: 1px solid #e5e5e5; border-radius: 10px; padding: 1.75rem; background: #fff; }
  .card.featured { border-color: #0366d6; box-shadow: 0 0 0 2px #0366d6; }
  .card h2 { font-size: 1.3rem; margin-bottom: 0.25rem; }
  .price { font-size: 2rem; font-weight: 700; margin: 0.75rem 0 0.25rem; }
  .price .period { font-size: 0.9rem; font-weight: 400; color: #666; }
  .desc { color: #555; font-size: 0.9rem; margin-bottom: 1rem; }
  ul { list-style: none; padding: 0; margin-bottom: 1.5rem; }
  li { padding: 0.3rem 0; font-size: 0.95rem; }
  li::before { content: "\\2713\\00a0"; color: #2ea043; font-weight: 700; }
  .btn { display: inline-block; padding: 0.6rem 1.5rem; border-radius: 6px;
         text-decoration: none; font-weight: 500; font-size: 0.95rem; text-align: center;
         width: 100%; }
  .btn-primary { background: #0366d6; color: #fff; }
  .btn-primary:hover { background: #0255b3; }
  .btn-secondary { background: #f5f5f5; color: #333; border: 1px solid #ddd; }
  .btn-secondary:hover { background: #eee; }
  .note { max-width: 960px; margin: 0 auto; padding: 0 1rem 2rem; text-align: center;
          color: #666; font-size: 0.9rem; }
  footer { padding: 1.5rem 1rem; text-align: center; color: #777; font-size: 0.9rem;
           border-top: 1px solid #eee; }
  a { color: #0366d6; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>

<div class="header">
  <h1>Pricing</h1>
  <p>Raw data is always free. Monetize convenience, not the data.</p>
</div>

<div class="grid">
  <div class="card">
    <h2>Free</h2>
    <div class="price">$0</div>
    <div class="desc">For researchers, journalists, NGOs, and indie developers</div>
    <ul>
      <li>100 requests/minute</li>
      <li>All read endpoints</li>
      <li>CSV &amp; JSON export</li>
      <li>Discrepancy Explorer</li>
      <li>No signup required</li>
    </ul>
    <a class="btn btn-secondary" href="/quickstart">Get Started</a>
  </div>

  <div class="card featured">
    <h2>Pro</h2>
    <div class="price">$149&ndash;299<span class="period">/mo</span></div>
    <div class="desc">For climate tech developers, small funds, and consultants</div>
    <ul>
      <li>1,000 requests/minute</li>
      <li>Bulk data export</li>
      <li>Webhooks for new data</li>
      <li>Historical snapshots</li>
      <li>Priority support</li>
    </ul>
    <a class="btn btn-primary" href="/enterprise">Request Access</a>
  </div>

  <div class="card">
    <h2>Enterprise</h2>
    <div class="price">$500&ndash;2K<span class="period">/mo</span></div>
    <div class="desc">For compliance consultants, ESG teams, and data aggregators</div>
    <ul>
      <li>Unlimited requests</li>
      <li>SLA guarantee</li>
      <li>Custom integrations</li>
      <li>White-label options</li>
      <li>Dedicated support</li>
    </ul>
    <a class="btn btn-primary" href="/enterprise">Contact Us</a>
  </div>
</div>

<p class="note">
  All raw data is also available as free monthly open data dumps on
  <a href="https://github.com/emissions-audit/emissions-tracker">GitHub</a>.
  We monetize convenience and real-time access, not the data itself.
</p>

<footer>
  <a href="/landing">Home</a> &middot;
  <a href="/quickstart">API Docs</a> &middot;
  <a href="/enterprise">Enterprise</a> &middot;
  <a href="https://github.com/emissions-audit/emissions-tracker">GitHub</a>
</footer>

</body>
</html>
"""


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["pages"])

    @router.get("/pricing", response_class=HTMLResponse)
    def pricing() -> HTMLResponse:
        return HTMLResponse(content=_PRICING_HTML, status_code=200)

    return router
