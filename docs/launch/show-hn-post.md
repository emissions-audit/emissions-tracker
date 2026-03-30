# Show HN Draft

**Title:** Show HN: Open-source API that cross-validates corporate emissions against satellite data

**Body:**

I built an open-source tool that compares what companies *report* as their emissions (SEC filings, CDP disclosures) against what satellites *actually measure* (Climate TRACE data). Discrepancies get flagged red/yellow/green.

The data to hold companies accountable exists, but it's scattered across PDFs, paywalled databases ($25K-$200K/year at Bloomberg/MSCI), and inconsistent formats. This normalizes it all into a free REST API.

V1 covers 20+ energy companies across 3 years with 4 independent sources. It's the sector where data is richest and discrepancies are largest.

**What makes this different from existing tools:**

- Bloomberg/MSCI/Refinitiv repackage what companies *say* — they can't flag greenwashing because their corporate clients pay them
- Climate TRACE measures real emissions but only at asset level — no corporate roll-ups or API for comparison
- CDP collects voluntary disclosures but takes them at face value
- This is the first tool that *compares* self-reported vs independent and flags the gap

**Stack:** Python 3.12, FastAPI, PostgreSQL, Docker. ~60 tests. MIT licensed.

**Links:**
- GitHub: https://github.com/cphalpert/emissions-tracker
- API docs: [hosted-url]/docs
- Landing page: https://cphalpert.github.io/emissions-tracker

Happy to answer questions about the data methodology, cross-validation algorithm, or anything else.
