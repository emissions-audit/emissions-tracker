import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    ticker: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str] = mapped_column(String(50))
    subsector: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(2))
    isin: Mapped[str | None] = mapped_column(String(12))
    website: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emissions: Mapped[list["Emission"]] = relationship(back_populates="company")
    filings: Mapped[list["Filing"]] = relationship(back_populates="company")
    pledges: Mapped[list["Pledge"]] = relationship(back_populates="company")


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    year: Mapped[int] = mapped_column(Integer)
    filing_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parser_used: Mapped[str] = mapped_column(String(20))
    raw_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="filings")


class Emission(Base):
    __tablename__ = "emissions"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "scope", "source_id", name="uq_emission_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    year: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(10))
    value_mt_co2e: Mapped[float] = mapped_column(Numeric(precision=20, scale=2))
    methodology: Mapped[str | None] = mapped_column(String(50))
    verified: Mapped[bool | None] = mapped_column(Boolean)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("filings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="emissions")
    source: Mapped["Filing | None"] = relationship()


class Pledge(Base):
    __tablename__ = "pledges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    pledge_type: Mapped[str] = mapped_column(String(50))
    target_year: Mapped[int | None] = mapped_column(Integer)
    target_scope: Mapped[str | None] = mapped_column(String(50))
    target_reduction_pct: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=2))
    baseline_year: Mapped[int | None] = mapped_column(Integer)
    baseline_value_mt_co2e: Mapped[float | None] = mapped_column(Numeric(precision=20, scale=2))
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("filings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="pledges")
    source: Mapped["Filing | None"] = relationship()


class DataPoint(Base):
    __tablename__ = "data_points"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    year: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Numeric(precision=20, scale=4))
    unit: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("filings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrossValidation(Base):
    __tablename__ = "cross_validations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    year: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(10))
    source_count: Mapped[int] = mapped_column(Integer)
    min_value: Mapped[float] = mapped_column(Numeric(precision=20, scale=2))
    max_value: Mapped[float] = mapped_column(Numeric(precision=20, scale=2))
    spread_pct: Mapped[float] = mapped_column(Numeric(precision=12, scale=2))
    flag: Mapped[str] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship()
    entries: Mapped[list["SourceEntry"]] = relationship(back_populates="cross_validation")


class SourceEntry(Base):
    __tablename__ = "source_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cross_validation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cross_validations.id"))
    source_type: Mapped[str] = mapped_column(String(20))
    value_mt_co2e: Mapped[float] = mapped_column(Numeric(precision=20, scale=2))
    filing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("filings.id"))

    cross_validation: Mapped["CrossValidation"] = relationship(back_populates="entries")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    use_case: Mapped[str | None] = mapped_column(String(500))
    tier: Mapped[str] = mapped_column(String(20), default="free")
    rate_limit: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    endpoint: Mapped[str] = mapped_column(String(500))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int] = mapped_column(Integer)
    response_time_ms: Mapped[float] = mapped_column(Numeric(precision=10, scale=2))
    api_key_hash: Mapped[str | None] = mapped_column(String(16))
    tier: Mapped[str] = mapped_column(String(20), default="anonymous")
    client_ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoverageSnapshot(Base):
    __tablename__ = "coverage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trigger: Mapped[str] = mapped_column(String(20))  # post_ingest, post_validate, manual
    source_filter: Mapped[str | None] = mapped_column(String(50))

    total_companies: Mapped[int] = mapped_column(Integer)
    total_emissions: Mapped[int] = mapped_column(Integer)
    total_filings: Mapped[int] = mapped_column(Integer)
    total_cross_validations: Mapped[int] = mapped_column(Integer)
    year_min: Mapped[int | None] = mapped_column(Integer)
    year_max: Mapped[int | None] = mapped_column(Integer)

    by_source_year: Mapped[dict] = mapped_column(JSONB)
    by_company_source: Mapped[dict] = mapped_column(JSONB)
    by_company_year: Mapped[dict] = mapped_column(JSONB)

    cv_by_flag: Mapped[dict] = mapped_column(JSONB)
    cv_coverage_pct: Mapped[float] = mapped_column(Numeric(precision=5, scale=2))

    alerts: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
