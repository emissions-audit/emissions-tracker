# Cross-Validation: Exxon Mobil (2023)

In 2023, Exxon Mobil Corp (XOM) told the EPA its US facilities emitted **124.8 million tCO2e**. Climate TRACE, using satellite observation and asset-level modeling of XOM-owned infrastructure worldwide, measured **168.4 million tCO2e** — a **35% gap** of roughly **43.6 million tCO2e**. That's the annual emissions of a mid-sized European country hiding in the seam between two reporting regimes. Until now, no free public tool put the two numbers next to each other.

## Side-by-side

|                 | EPA GHGRP              | Climate TRACE v6       | Delta              |
|-----------------|------------------------|------------------------|--------------------|
| 2023 emissions  | 124.8 Mt CO2e          | 168.4 Mt CO2e          | +43.6 Mt (+35%)    |
| Scope           | Scope 1, US facilities | Owned assets, global   | —                  |
| Methodology     | Self-reported          | Satellite + modeled    | —                  |

## Why these disagree

The 35% gap is **not** evidence of fraud. It's a stack of legitimate scope and methodology differences that compound:

- **Geographic scope.** EPA GHGRP covers only US-based facilities above the reporting threshold. Climate TRACE covers XOM-owned assets globally, including refineries, wells, and LNG terminals in Canada, Guyana, Nigeria, Qatar, and elsewhere.
- **Asset vs. facility boundary.** GHGRP aggregates at the regulatory facility level (smokestacks on site). Climate TRACE measures entire owned production assets — including upstream flaring and venting at wells that fall outside GHGRP's facility definition.
- **Measurement method.** GHGRP is self-reported using EPA calculation methods. Climate TRACE uses satellite observations of plumes and thermal signatures combined with physical modeling, which tends to catch methane and flaring that self-reports miss.
- **Scope 1 only.** Neither number includes Scope 2 (purchased electricity) or Scope 3 (product use). Exxon's Scope 3 is roughly an order of magnitude larger than either figure here.

The journalist story isn't *"Exxon is lying."* It's *"Why has no free public tool put these two numbers side-by-side before — and what does it mean that the US regulator only sees a fraction of what satellites can see?"*

## Reproduce this query

```bash
# EPA GHGRP side
curl "https://emissions-tracker-production.up.railway.app/v1/emissions?ticker=XOM&year=2023&source=epa_ghgrp"

# Climate TRACE side
curl "https://emissions-tracker-production.up.railway.app/v1/emissions?ticker=XOM&year=2023&source=climate_trace"
```

Both endpoints return JSON with the underlying facility/asset rows, the reporting year, and provenance metadata so you can audit each number independently.

## Provenance

- **EPA Greenhouse Gas Reporting Program (GHGRP)** — facility-level US emissions self-reported under 40 CFR Part 98. Canonical entry point: <https://www.epa.gov/ghgreporting>
- **Climate TRACE** — independent coalition publishing asset-level global emissions from satellite and remote sensing. Canonical entry point: <https://climatetrace.org>

This artifact uses v6 of the Climate TRACE oil & gas dataset and the 2023 GHGRP public dataset as ingested by the Emissions Tracker pipeline. See the repo for ingestion timestamps and raw-row hashes.

---

Back to [main README](../README.md).
