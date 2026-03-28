import json

import httpx
import pdfplumber

from src.pipeline.sources.base import BaseSource, RawEmission


def build_extraction_prompt(text: str) -> str:
    return f"""Extract greenhouse gas emissions data from this sustainability report text.

Return a JSON array of objects with these fields:
- "scope": one of "Scope 1", "Scope 2", "Scope 3", "Total"
- "value": numeric value (no commas, no units)
- "unit": one of "mt_co2e", "kt_co2e", "t_co2e"
- "year": integer year
- "methodology": string or null (e.g., "ghg_protocol", "iso_14064")
- "verified": boolean or null

Only include data that is clearly stated as greenhouse gas emissions.
If no emissions data is found, return an empty array [].
Return ONLY the JSON array, no other text.

Sustainability report text:
{text[:15000]}"""


def parse_llm_response(ticker: str, response_text: str, source_url: str) -> list[RawEmission]:
    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return []

    if not isinstance(data, list):
        return []

    results = []
    for entry in data:
        try:
            results.append(
                RawEmission(
                    company_ticker=ticker,
                    year=int(entry["year"]),
                    scope=entry["scope"],
                    value=float(entry["value"]),
                    unit=entry.get("unit", "mt_co2e"),
                    methodology=entry.get("methodology"),
                    verified=entry.get("verified"),
                    source_url=source_url,
                    filing_type="sustainability_report",
                    parser_used="llm",
                )
            )
        except (KeyError, ValueError):
            continue

    return results


class PdfSource(BaseSource):
    name = "pdf"

    def __init__(self, anthropic_api_key: str = ""):
        self.api_key = anthropic_api_key

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        return []

    async def ingest_pdf(self, ticker: str, pdf_path: str, source_url: str) -> list[RawEmission]:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if not text.strip():
            return []

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        prompt = build_extraction_prompt(text)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        return parse_llm_response(ticker, response_text, source_url)
