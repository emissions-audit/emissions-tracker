import asyncio
from typing import Optional

import typer

app = typer.Typer(name="emissions-pipeline", help="Corporate emissions data pipeline")


@app.command()
def ingest(
    source: str = typer.Argument(help="Source to ingest: edgar, climate_trace, cdp, pdf"),
    tickers: Optional[str] = typer.Option(None, help="Comma-separated tickers (default: all)"),
    years: str = typer.Option("2022,2023,2024", help="Comma-separated years"),
):
    """Fetch, parse, normalize, and load emissions data from a source."""
    ticker_list = tickers.split(",") if tickers else []
    year_list = [int(y.strip()) for y in years.split(",")]
    typer.echo(f"Ingesting from {source} for tickers={ticker_list}, years={year_list}")
    asyncio.run(_ingest(source, ticker_list, year_list))


async def _ingest(source: str, tickers: list[str], years: list[int]):
    typer.echo(f"Source '{source}' not yet implemented")


@app.command()
def validate():
    """Run cross-validation on all emissions data."""
    typer.echo("Running cross-validation...")
    asyncio.run(_validate())


async def _validate():
    typer.echo("Validation not yet implemented")


@app.command()
def seed():
    """Seed the companies table with V1 energy companies."""
    typer.echo("Seeding companies...")
    asyncio.run(_seed())


async def _seed():
    typer.echo("Seed not yet implemented")


if __name__ == "__main__":
    app()
