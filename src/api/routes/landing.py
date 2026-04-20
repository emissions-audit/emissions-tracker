from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


_LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Emissions Tracker &mdash; Open-Source Corporate Emissions Database</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         color: #222; line-height: 1.6; }
  .hero { text-align: center; padding: 3rem 1rem 2rem; background: #f8fafb; border-bottom: 1px solid #e5e5e5; }
  .hero h1 { font-size: 2rem; margin-bottom: 0.5rem; }
  .hero .tagline { color: #555; font-size: 1.1rem; max-width: 640px; margin: 0 auto 2rem; }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                 gap: 1rem; max-width: 720px; margin: 0 auto; }
  .stat-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
               padding: 1.25rem 1rem; text-align: center; }
  .stat-value { font-size: 1.8rem; font-weight: 700; color: #0366d6; }
  .stat-label { font-size: 0.85rem; color: #666; margin-top: 0.25rem; }
  .loading { color: #aaa; }
  .content { max-width: 820px; margin: 2rem auto; padding: 0 1rem; }
  h2 { font-size: 1.3rem; margin-top: 2rem; margin-bottom: 0.5rem; border-bottom: 1px solid #eee;
       padding-bottom: 0.25rem; }
  .cta { display: inline-block; margin: 0.5rem 0.5rem 0 0; padding: 0.6rem 1.2rem;
         border-radius: 6px; text-decoration: none; font-weight: 500; font-size: 0.95rem; }
  .cta-primary { background: #0366d6; color: #fff; }
  .cta-primary:hover { background: #0255b3; }
  .cta-secondary { background: #f5f5f5; color: #333; border: 1px solid #ddd; }
  .cta-secondary:hover { background: #eee; }
  footer { margin-top: 3rem; padding: 1.5rem 1rem; text-align: center; color: #777;
           font-size: 0.9rem; border-top: 1px solid #eee; }
  a { color: #0366d6; text-decoration: none; }
  a:hover { text-decoration: underline; }
  /* ET-78: social-proof widget */
  .launch-proof { display: none; margin: 1.25rem auto 0; max-width: 720px;
                   padding: 0.5rem 1rem; text-align: center; color: #555;
                   font-size: 0.92rem; line-height: 1.5; }
  .launch-proof.visible { display: flex; flex-wrap: wrap; justify-content: center;
                           gap: 0.35rem 0.9rem; }
  .launch-proof .lp-sep { color: #bbb; }
  .launch-proof .lp-item { white-space: nowrap; }
  @media (max-width: 420px) {
    .launch-proof { font-size: 0.85rem; }
    .launch-proof .lp-sep { display: none; }
  }
</style>
</head>
<body>

<div class="hero">
  <h1>Emissions Tracker</h1>
  <p class="tagline">Cross-validated US corporate emissions &mdash; independent, free, after the EPA's exit.
  We aggregate public disclosures and cross-validate self-reported figures against independent measurements.</p>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value" id="companies">
        <span class="loading">&mdash;</span>
      </div>
      <div class="stat-label">Companies Tracked</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="sources">
        <span class="loading">&mdash;</span>
      </div>
      <div class="stat-label">Data Sources</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="discrepancies">
        <span class="loading">&mdash;</span>
      </div>
      <div class="stat-label">Discrepancies Found</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="stars">
        <span class="loading">&mdash;</span>
      </div>
      <div class="stat-label">GitHub Stars</div>
    </div>
  </div>

  <!-- ET-78: live social-proof counter (hidden until /v1/metrics/launch responds) -->
  <div id="launch-proof" class="launch-proof" aria-live="polite"></div>
</div>

<div class="content">
  <div>
    <a class="cta cta-primary" href="/quickstart">API Quickstart</a>
    <a class="cta cta-secondary" href="/discrepancies">Discrepancy Explorer</a>
    <a class="cta cta-secondary" href="https://github.com/emissions-audit/emissions-tracker">GitHub</a>
  </div>

  <h2>What is this?</h2>
  <p>~100 companies produce ~71% of global emissions. The data to hold them accountable exists but is
  scattered across PDFs, inconsistent formats, and paywalled databases. This project aggregates it all
  into a free, searchable, developer-friendly API &mdash; and cross-validates what companies report
  against what satellites and regulators measure.</p>

  <h2>Data Sources</h2>
  <p>SEC EDGAR, Climate TRACE, CDP, EPA GHGRP, EU ETS, and corporate sustainability reports &mdash;
  normalized, compared, and flagged when numbers don't add up.</p>

  <h2>For Developers</h2>
  <p>Clean REST API with JSON responses, CSV/JSON export, cross-validation endpoints, and discrepancy
  detection. Free tier: 100 req/min, all read endpoints, no signup required.</p>
</div>

<footer>
  Open source &middot;
  <a href="https://github.com/emissions-audit/emissions-tracker">GitHub</a> &middot;
  <a href="/quickstart">API Docs</a> &middot;
  <a href="/docs">Swagger</a>
</footer>

<script>
(function() {
  function set(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  fetch('/v1/stats')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      set('companies', d.company_count || 0);
    })
    .catch(function() { set('companies', '?'); });

  fetch('/v1/metrics')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.coverage) {
        set('sources', d.coverage.sources_active || 0);
      } else {
        set('sources', '?');
      }
    })
    .catch(function() { set('sources', '?'); });

  fetch('/v1/discrepancies?limit=1&offset=0')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      set('discrepancies', d.total != null ? d.total : '?');
    })
    .catch(function() { set('discrepancies', '?'); });

  fetch('/v1/project-stats')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      set('stars', d.stars != null ? d.stars : '?');
    })
    .catch(function() { set('stars', '?'); });

  // Auto-refresh every 60 seconds
  setInterval(function() {
    fetch('/v1/project-stats')
      .then(function(r) { return r.json(); })
      .then(function(d) { set('stars', d.stars != null ? d.stars : '?'); })
      .catch(function() {});
    fetch('/v1/stats')
      .then(function(r) { return r.json(); })
      .then(function(d) { set('companies', d.company_count || 0); })
      .catch(function() {});
  }, 60000);
})();

// ET-78: social-proof widget — fetch /v1/metrics/launch and render a live
// counter line. Hides individual fields when null/0 and hides the whole
// widget if nothing is worth showing. Graceful on fetch failure.
(function() {
  var el = document.getElementById('launch-proof');
  if (!el) return;

  function renderProof(data) {
    if (!data) { el.className = 'launch-proof'; el.textContent = ''; return; }
    var parts = [];
    if (data.stars_total != null && data.stars_total > 0) {
      parts.push('<span class="lp-item">&#9733; ' + data.stars_total + ' GitHub stars</span>');
    }
    if (data.citations_mentioned != null && data.citations_mentioned > 0) {
      parts.push('<span class="lp-item">' + data.citations_mentioned + ' citations this week</span>');
    }
    if (parts.length === 0) {
      el.className = 'launch-proof';
      el.textContent = '';
      return;
    }
    el.innerHTML = parts.join('<span class="lp-sep">&middot;</span>');
    el.className = 'launch-proof visible';
  }

  function loadProof() {
    fetch('/v1/metrics/launch')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(renderProof)
      .catch(function() { /* leave widget hidden on error */ });
  }

  loadProof();
  setInterval(loadProof, 30000);
})();
</script>

</body>
</html>
"""


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["pages"])

    @router.get("/landing", response_class=HTMLResponse)
    def landing() -> HTMLResponse:
        return HTMLResponse(content=_LANDING_HTML, status_code=200)

    return router
