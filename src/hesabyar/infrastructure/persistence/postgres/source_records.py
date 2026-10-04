"""SQLAlchemy model + repository for the legal-source registry (ARCHITECTURE.md §1.3)."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hesabyar.domain.tax.sources import SourceDomain, SourceRecord, VerificationStatus
from hesabyar.infrastructure.persistence.postgres.models import Base


class SourceRecordModel(Base):
    """Persisted legal-source registry row.

    Global (non-tenant) reference data: legal sources are shared facts, not
    tenant business objects, so this table intentionally has no tenant_id.
    """

    __tablename__ = "legal_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Stable source identifier")
    domain: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="tax | accounting_standard | moadian_protocol"
    )
    authority: Mapped[str] = mapped_column(String(256), nullable=False, comment="Issuing authority")
    document_number_or_version: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retrieved_at: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    def to_domain(self) -> SourceRecord:
        """Map the ORM row to the domain SourceRecord value object."""
        return SourceRecord(
            source_id=self.source_id,
            domain=SourceDomain(self.domain),
            authority=self.authority,
            document_number_or_version=self.document_number_or_version,
            title=self.title,
            published_at=self.published_at,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            retrieved_at=self.retrieved_at,
            canonical_url=self.canonical_url,
            snapshot_uri=self.snapshot_uri,
            sha256=self.sha256,
            verification_status=VerificationStatus(self.verification_status),
            verified_by=self.verified_by,
            verified_at=self.verified_at,
            notes=self.notes,
        )

    @classmethod
    def from_domain(cls, rec: SourceRecord) -> SourceRecordModel:
        """Build an ORM row from a domain SourceRecord."""
        return cls(
            source_id=rec.source_id,
            domain=rec.domain.value,
            authority=rec.authority,
            document_number_or_version=rec.document_number_or_version,
            title=rec.title,
            published_at=rec.published_at,
            effective_from=rec.effective_from,
            effective_to=rec.effective_to,
            retrieved_at=rec.retrieved_at,
            canonical_url=rec.canonical_url,
            snapshot_uri=rec.snapshot_uri,
            sha256=rec.sha256,
            verification_status=rec.verification_status.value,
            verified_by=rec.verified_by,
            verified_at=rec.verified_at,
            notes=rec.notes,
        )


class SourceRecordRepository:
    """Session-bound repository for SourceRecord rows (global reference data)."""

    def __init__(self, session) -> None:  # noqa: ANN001 — Session typed loosely to avoid infra import cycles in domain tests
        self._session = session

    def get(self, source_id: str) -> SourceRecord | None:
        """Fetch one record by id, or None."""
        row = self._session.get(SourceRecordModel, source_id)
        return None if row is None else row.to_domain()

    def list_all(self) -> list[SourceRecord]:
        """All registered records."""
        rows = self._session.query(SourceRecordModel).order_by(SourceRecordModel.source_id).all()
        return [r.to_domain() for r in rows]

    def upsert(self, rec: SourceRecord) -> SourceRecord:
        """Insert or update one record."""
        row = self._session.get(SourceRecordModel, rec.source_id)
        if row is None:
            row = SourceRecordModel.from_domain(rec)
            self._session.add(row)
        else:
            for field, value in SourceRecordModel.from_domain(rec).__dict__.items():
                if not field.startswith("_") and field != "source_id":
                    setattr(row, field, value)
        self._session.flush()
        return rec


__all__ = ["SourceRecordModel", "SourceRecordRepository"]
