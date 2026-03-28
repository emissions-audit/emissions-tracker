import uuid

from src.shared.models import Company, Filing, Emission, Pledge, DataPoint, CrossValidation, SourceEntry, ApiKey


def test_create_company(db_session):
    company = Company(
        id=uuid.uuid4(),
        name="Shell plc",
        ticker="SHEL",
        sector="energy",
        subsector="oil_gas_integrated",
        country="GB",
        isin="GB00BP6MXD84",
        website="https://www.shell.com",
    )
    db_session.add(company)
    db_session.commit()

    result = db_session.query(Company).first()
    assert result.name == "Shell plc"
    assert result.ticker == "SHEL"
    assert result.country == "GB"


def test_create_filing_and_emission(db_session):
    company_id = uuid.uuid4()
    filing_id = uuid.uuid4()

    company = Company(id=company_id, name="ExxonMobil", ticker="XOM",
                      sector="energy", subsector="oil_gas_integrated", country="US")
    filing = Filing(id=filing_id, company_id=company_id, year=2023,
                    filing_type="10k_xbrl", source_url="https://sec.gov/example",
                    parser_used="xbrl", raw_hash="abc123")
    emission = Emission(id=uuid.uuid4(), company_id=company_id, year=2023,
                        scope="1", value_mt_co2e=120_000_000.0,
                        methodology="ghg_protocol", verified=True, source_id=filing_id)

    db_session.add_all([company, filing, emission])
    db_session.commit()

    result = db_session.query(Emission).first()
    assert result.scope == "1"
    assert result.value_mt_co2e == 120_000_000.0
    assert result.verified is True


def test_create_cross_validation(db_session):
    company_id = uuid.uuid4()
    cv_id = uuid.uuid4()

    company = Company(id=company_id, name="BP", ticker="BP", sector="energy",
                      subsector="oil_gas_integrated", country="GB")
    cv = CrossValidation(id=cv_id, company_id=company_id, year=2023, scope="1",
                         source_count=3, min_value=90_000_000.0, max_value=120_000_000.0,
                         spread_pct=33.3, flag="red")
    entry = SourceEntry(id=uuid.uuid4(), cross_validation_id=cv_id,
                        source_type="regulatory", value_mt_co2e=100_000_000.0)

    db_session.add_all([company, cv, entry])
    db_session.commit()

    result = db_session.query(CrossValidation).first()
    assert result.flag == "red"
    assert result.source_count == 3


def test_create_api_key(db_session):
    key = ApiKey(id=uuid.uuid4(), key_hash="sha256hashvalue", email="dev@example.com",
                 tier="free", rate_limit=100)
    db_session.add(key)
    db_session.commit()

    result = db_session.query(ApiKey).first()
    assert result.tier == "free"
    assert result.rate_limit == 100
