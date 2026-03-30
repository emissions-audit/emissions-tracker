# Reddit Post Draft

**Subreddit:** r/sustainability (primary), r/dataisbeautiful (secondary), r/datasets (secondary)

**Title:** I built a free, open-source tool that cross-validates corporate emissions reports against satellite data — and flags when companies underreport

**Body (r/sustainability):**

~100 companies produce ~71% of global emissions. They self-report their numbers to regulators and disclosure platforms, and for the most part, nobody checks.

I built an open-source database + API that pulls emissions data from 4 independent sources:
- SEC EDGAR (regulatory filings)
- Climate TRACE (satellite-derived measurements)
- CDP (voluntary corporate disclosure)
- Sustainability report PDFs (LLM-extracted)

Then it *cross-validates* them. When ExxonMobil's SEC filing says one thing but Climate TRACE satellite data says another, the discrepancy gets flagged with a severity score.

V1 covers 20+ energy companies, 3 years of data. Everything is free, MIT licensed, and self-hostable.

Why does this matter? Tools like Bloomberg ESG ($25K+/year) and MSCI just repackage what companies report — they can't flag greenwashing because those companies are their clients. This tool has no corporate clients to protect.

**Links:**
- GitHub: [link]
- Try the API: [link]/docs
- Free data dumps: [link]

Would love feedback from anyone working in sustainability, climate journalism, or ESG research.
