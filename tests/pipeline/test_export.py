import csv
import json
import uuid

import pytest
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.models import (
    Base, Company, Emission, Filing, CrossValidation, SourceEntry,
)
from src.pipeline.export import (
    export_companies_json,
    export_companies_csv,
    export_emissions_json,
    export_emissions_csv,
    export_cross_validations_json,
    export_all,
)


@pytest.fixture
def export_session():
    engine = create_sync_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()

    shell_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    filing_id = uuid.UUID("00000000-0000-0000-0000-000000000010")

    session.add_all([
        Company(id=shell_id, name="Shell plc", ticker="SHEL", sector="energy",
                subsector="oil_gas_integrated", country="GB", isin="GB00BP6MXD84"),
        Filing(id=filing_id, company_id=shell_id, year=2023,
               filing_type="10k_xbrl", parser_used="xbrl"),
        Emission(id=uuid.uuid4(), company_id=shell_id, year=2023, scope="1",
                 value_mt_co2e=68_000_000, source_id=filing_id),
        Emission(id=uuid.uuid4(), company_id=shell_id, year=2023, scope="2",
                 value_mt_co2e=10_000_000, source_id=filing_id),
    ])
    session.commit()

    cv_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
    session.add_all([
        CrossValidation(id=cv_id, company_id=shell_id, year=2023, scope="1",
                        source_count=2, min_value=65_000_000, max_value=72_000_000,
                        spread_pct=10.77, flag="yellow"),
        SourceEntry(id=uuid.uuid4(), cross_validation_id=cv_id,
                    source_type="regulatory", value_mt_co2e=65_000_000,
                    filing_id=filing_id),
    ])
    session.commit()
    yield session
    session.close()


class TestExportCompaniesJson:
    def test_returns_list_of_dicts(self, export_session):
        result = export_companies_json(export_session)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["ticker"] == "SHEL"
        assert result[0]["name"] == "Shell plc"

    def test_includes_all_fields(self, export_session):
        result = export_companies_json(export_session)
        company = result[0]
        for field in ["id", "name", "ticker", "sector", "subsector", "country", "isin"]:
            assert field in company


class TestExportCompaniesCsv:
    def test_writes_csv_file(self, export_session, tmp_path):
        output_path = tmp_path / "companies.csv"
        export_companies_csv(export_session, str(output_path))
        assert output_path.exists()
        with open(output_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["ticker"] == "SHEL"


class TestExportEmissionsJson:
    def test_returns_list_with_company_info(self, export_session):
        result = export_emissions_json(export_session)
        assert len(result) == 2
        assert all(e["company_name"] == "Shell plc" for e in result)
        assert all(e["company_ticker"] == "SHEL" for e in result)

    def test_includes_value_and_scope(self, export_session):
        result = export_emissions_json(export_session)
        scopes = {e["scope"] for e in result}
        assert "1" in scopes
        assert "2" in scopes


class TestExportEmissionsCsv:
    def test_writes_csv_file(self, export_session, tmp_path):
        output_path = tmp_path / "emissions.csv"
        export_emissions_csv(export_session, str(output_path))
        assert output_path.exists()
        with open(output_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2


class TestExportCrossValidationsJson:
    def test_returns_list_with_flag(self, export_session):
        result = export_cross_validations_json(export_session)
        assert len(result) == 1
        assert result[0]["flag"] == "yellow"
        assert result[0]["spread_pct"] == 10.77


class TestExportAll:
    def test_creates_all_files(self, export_session, tmp_path):
        files = export_all(export_session, str(tmp_path))
        assert len(files) == 6
        for path in files.values():
            assert (tmp_path / path.split("/")[-1]).exists() or \
                   (tmp_path / path.split("\\")[-1]).exists()

    def test_json_files_are_valid(self, export_session, tmp_path):
        export_all(export_session, str(tmp_path))
        for name in ["companies.json", "emissions.json", "cross_validations.json"]:
            data = json.loads((tmp_path / name).read_text())
            assert isinstance(data, list)
            assert len(data) > 0


from unittest.mock import patch
from typer.testing import CliRunner
from src.pipeline.cli import app as cli_app

runner = CliRunner()


class TestExportCliCommand:
    @patch("src.pipeline.cli._get_sync_session")
    @patch("src.pipeline.cli.export_all")
    def test_export_command_calls_export_all(self, mock_export_all, mock_session):
        mock_export_all.return_value = {
            "companies_json": "/tmp/companies.json",
            "emissions_json": "/tmp/emissions.json",
            "cross_validations_json": "/tmp/cross_validations.json",
            "companies_csv": "/tmp/companies.csv",
            "emissions_csv": "/tmp/emissions.csv",
            "cross_validations_csv": "/tmp/cross_validations.csv",
        }
        result = runner.invoke(cli_app, ["export", "--output", "/tmp/export"])
        assert result.exit_code == 0
        mock_export_all.assert_called_once()
