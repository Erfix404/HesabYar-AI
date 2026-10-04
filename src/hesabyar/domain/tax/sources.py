"""Legal source registry — provenance records for every legal/tax fact (ARCHITECTURE.md §1.3).

Every legal, tax, or protocol fact used by production logic MUST have a SourceRecord.
Production logic may only treat a source as authoritative when
``verification_status`` is ``VERIFIED``. ``CORROBORATED_CURRENT`` sources are usable
for advisory answers only, and any user-facing conclusion must echo
``source_id`` and ``verification_status``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml

from hesabyar.domain.common.errors import HesabYarError

_DATA_FILE = Path(__file__).parent / "data" / "sources.yaml"


class VerificationStatus(StrEnum):
    """Status of a legal source record.

    Mirrors docs/CURRENT_RULES_1405.md verification labels mapped onto the
    ARCHITECTURE.md §1.3 statuses: CORROBORATED_CURRENT is the documented
    "current per multiple reliable sources, snapshot not yet pinned" state.
    """

    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    CORROBORATED_CURRENT = "CORROBORATED_CURRENT"
    RETIRED = "RETIRED"
    DISPUTED = "DISPUTED"


class SourceDomain(StrEnum):
    """Which authority domain a legal source belongs to."""

    TAX = "tax"
    ACCOUNTING_STANDARD = "accounting_standard"
    MOADIAN_PROTOCOL = "moadian_protocol"


@dataclass(frozen=True)
class SourceRecord:
    """A registered, provenance-tracked legal source snapshot."""

    source_id: str
    domain: SourceDomain
    authority: str
    document_number_or_version: str
    title: str
    published_at: str | None
    effective_from: str | None
    effective_to: str | None
    retrieved_at: str
    canonical_url: str
    snapshot_uri: str | None
    sha256: str | None
    verification_status: VerificationStatus
    verified_by: str | None
    verified_at: str | None
    notes: str = ""

    @property
    def is_production_usable(self) -> bool:
        """Production logic may rely on this source only when VERIFIED."""
        return self.verification_status == VerificationStatus.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (used by MCP/CLI output for provenance echo)."""
        return {
            "source_id": self.source_id,
            "domain": self.domain.value,
            "authority": self.authority,
            "document_number_or_version": self.document_number_or_version,
            "title": self.title,
            "published_at": self.published_at,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "retrieved_at": self.retrieved_at,
            "canonical_url": self.canonical_url,
            "snapshot_uri": self.snapshot_uri,
            "sha256": self.sha256,
            "verification_status": self.verification_status.value,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "notes": self.notes,
        }


class UnknownSourceError(HesabYarError):
    """Raised when a source_id is not present in the registry."""


def sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file (snapshot pinning helper)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SourceRegistry:
    """Loads and resolves legal source records from the bundled YAML registry."""

    def __init__(self, records: list[SourceRecord]) -> None:
        self._records = records
        self._by_id: dict[str, SourceRecord] = {}
        for rec in records:
            if rec.source_id in self._by_id:
                raise HesabYarError(
                    f"Duplicate source_id {rec.source_id!r} in registry.", code="DUPLICATE_SOURCE_ID"
                )
            self._by_id[rec.source_id] = rec

    @classmethod
    def load_default(cls) -> Self:
        """Load the bundled registry from sources.yaml."""
        raw = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}
        entries = raw.get("sources") or []
        return cls([_parse_source(entry) for entry in entries])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a registry from parsed YAML content (testing / external data)."""
        entries = data.get("sources") or []
        return cls([_parse_source(entry) for entry in entries])

    def get(self, source_id: str) -> SourceRecord:
        """Fetch a record by source_id; raises UnknownSourceError when missing."""
        rec = self._by_id.get(source_id)
        if rec is None:
            raise UnknownSourceError(f"Unknown source_id: {source_id!r}", code="UNKNOWN_SOURCE")
        return rec

    def require_verified(self, source_id: str) -> SourceRecord:
        """Fetch a record that must be VERIFIED; fail-closed otherwise."""
        rec = self.get(source_id)
        if not rec.is_production_usable:
            raise HesabYarError(
                f"Source {source_id!r} is {rec.verification_status.value}, not VERIFIED; "
                "production logic may not rely on it.",
                code="SOURCE_NOT_VERIFIED",
            )
        return rec

    def all_records(self) -> list[SourceRecord]:
        """Return all registered records."""
        return list(self._records)

    def provenance_echo(self, source_id: str) -> dict[str, str]:
        """A minimal provenance block to embed in user-facing output."""
        rec = self.get(source_id)
        return {
            "source_id": rec.source_id,
            "verification_status": rec.verification_status.value,
            "authority": rec.authority,
        }


def _parse_source(entry: dict[str, Any]) -> SourceRecord:
    return SourceRecord(
        source_id=str(entry["source_id"]),
        domain=SourceDomain(entry.get("domain", "tax")),
        authority=str(entry.get("authority", "")),
        document_number_or_version=str(entry.get("document_number_or_version", "")),
        title=str(entry.get("title", "")),
        published_at=entry.get("published_at"),
        effective_from=entry.get("effective_from"),
        effective_to=entry.get("effective_to"),
        retrieved_at=str(entry.get("retrieved_at", "")),
        canonical_url=str(entry.get("canonical_url", "")),
        snapshot_uri=entry.get("snapshot_uri"),
        sha256=entry.get("sha256"),
        verification_status=VerificationStatus(entry.get("verification_status", "DRAFT")),
        verified_by=entry.get("verified_by"),
        verified_at=entry.get("verified_at"),
        notes=str(entry.get("notes", "")),
    )


__all__ = [
    "SourceDomain",
    "SourceRecord",
    "SourceRegistry",
    "UnknownSourceError",
    "VerificationStatus",
    "sha256_of_file",
]
