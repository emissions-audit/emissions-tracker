from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import EnterpriseInquiry


_STYLE = """
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #222; line-height: 1.5; }
  h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
  .pitch { color: #555; margin-top: 0; font-size: 1.05rem; }
  label { display: block; margin-top: 1rem; font-weight: 600; font-size: 0.95rem; }
  input, textarea, select { width: 100%; padding: 0.5rem; margin-top: 0.25rem; border: 1px solid #ccc;
         border-radius: 4px; font-size: 0.95rem; font-family: inherit; }
  textarea { resize: vertical; min-height: 80px; }
  button { margin-top: 1.5rem; padding: 0.7rem 1.5rem; background: #0366d6; color: #fff;
           border: none; border-radius: 6px; font-size: 1rem; font-weight: 500; cursor: pointer; }
  button:hover { background: #0255b3; }
  .note { margin-top: 1rem; color: #666; font-size: 0.9rem; }
  footer { margin-top: 2.5rem; color: #777; font-size: 0.9rem; text-align: center; }
  a { color: #0366d6; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .success { background: #e6f9e6; border: 1px solid #b3e6b3; border-radius: 6px;
             padding: 1.5rem; text-align: center; margin-top: 2rem; }
  .success h2 { color: #2d7a2d; margin-bottom: 0.5rem; }
"""

_FORM_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Enterprise &mdash; Emissions Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{_STYLE}</style>
</head>
<body>

<h1>Enterprise Access</h1>
<p class="pitch">Unlimited API access, SLA, custom integrations, and white-label options
for compliance teams, ESG consultancies, and data aggregators.</p>

<form method="post" action="/enterprise">
  <label for="company_name">Company / Organization</label>
  <input type="text" id="company_name" name="company_name" required>

  <label for="email">Work Email</label>
  <input type="email" id="email" name="email" required>

  <label for="use_case">Use Case</label>
  <textarea id="use_case" name="use_case"
    placeholder="e.g., ESG compliance reporting, portfolio emissions monitoring, academic research..."></textarea>

  <label for="estimated_volume">Estimated Monthly API Volume</label>
  <select id="estimated_volume" name="estimated_volume">
    <option value="">Select...</option>
    <option value="<10K">&lt; 10K requests/month</option>
    <option value="10K-100K">10K &ndash; 100K requests/month</option>
    <option value="100K-1M">100K &ndash; 1M requests/month</option>
    <option value=">1M">&gt; 1M requests/month</option>
  </select>

  <button type="submit">Request Enterprise Access</button>
  <p class="note">We'll respond within 2 business days. No commitment required.</p>
</form>

<footer>
  <a href="/landing">Home</a> &middot;
  <a href="/pricing">Pricing</a> &middot;
  <a href="/quickstart">API Docs</a> &middot;
  <a href="https://github.com/emissions-audit/emissions-tracker">GitHub</a>
</footer>

</body>
</html>"""

_CONFIRM_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Thank You &mdash; Emissions Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{_STYLE}</style>
</head>
<body>

<div class="success">
  <h2>Thank you!</h2>
  <p>We've received your inquiry and will follow up within 2 business days.</p>
</div>

<footer>
  <a href="/landing">Home</a> &middot;
  <a href="/pricing">Pricing</a> &middot;
  <a href="/quickstart">API Docs</a>
</footer>

</body>
</html>"""


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["enterprise"])

    @router.get("/enterprise", response_class=HTMLResponse)
    def enterprise_form() -> HTMLResponse:
        return HTMLResponse(content=_FORM_HTML, status_code=200)

    @router.post("/enterprise", response_class=HTMLResponse)
    async def enterprise_submit(
        db: AsyncSession = get_db,
        company_name: str = Form(...),
        email: str = Form(...),
        use_case: str = Form(""),
        estimated_volume: str = Form(""),
    ) -> HTMLResponse:
        inquiry = EnterpriseInquiry(
            company_name=company_name,
            email=email,
            use_case=use_case or None,
            estimated_volume=estimated_volume or None,
        )
        db.add(inquiry)
        await db.commit()
        return HTMLResponse(content=_CONFIRM_HTML, status_code=200)

    return router
