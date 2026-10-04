"""Effective-dated Iranian tax parameter registry (legislation-as-code, OpenFisca-style).

Every parameter is a named series of intervals, each with a Jalali effective window
and a mandatory ``source_id`` into the legal-source registry. Resolving a parameter
for a date with no covering interval fails closed — there is no silent "latest value".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Self

import yaml

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.errors import HesabYarError
from hesabyar.domain.tax.sources import SourceRegistry, VerificationStatus

_DATA_FILE = Path(__file__).parent / "data" / "parameters.yaml"


class UnknownParameterError(HesabYarError):
    """Raised when a parameter name is not present in the registry."""


class ParameterNotEffectiveError(HesabYarError):
    """Raised when no interval of a parameter covers the requested date (fail-closed)."""


@dataclass(frozen=True)
class ParameterInterval:
    """One value of a parameter, valid over a Jalali effective window."""

    value: Decimal | int
    effective_from: str
    effective_to: str | None
    source_id: str
    note: str = ""


@dataclass(frozen=True)
class TaxParameter:
    """A named tax parameter with its effective-dated intervals."""

    name: str
    unit: str
    description: str
    intervals: list[ParameterInterval]

    def covering_interval(self, on_date: FiscalDate) -> ParameterInterval:
        """Return the interval covering ``on_date``; fail-closed when none does."""
        for interval in self.intervals:
            start = FiscalDate.from_jalali_str(interval.effective_from)
            end = (
                FiscalDate.from_jalali_str(interval.effective_to)
                if interval.effective_to is not None
                else None
            )
            if start.date <= on_date.date and (end is None or on_date.date <= end.date):
                return interval
        raise ParameterNotEffectiveError(
            f"Parameter {self.name!r} has no interval covering {on_date.to_jalali_str()}; "
            "refusing to guess a value (fail-closed).",
            code="PARAMETER_NOT_EFFECTIVE",
        )


@dataclass(frozen=True)
class ResolvedParameter:
    """The result of resolving a parameter for a specific date, with provenance."""

    name: str
    value: Decimal | int
    unit: str
    on_date: str
    effective_from: str
    effective_to: str | None
    source_id: str
    verification_status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for MCP/CLI output (provenance included)."""
        return {
            "name": self.name,
            "value": str(self.value),
            "unit": self.unit,
            "on_date": self.on_date,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "source_id": self.source_id,
            "verification_status": self.verification_status,
            "note": self.note,
        }


class ParameterRegistry:
    """Loads and resolves effective-dated tax parameters."""

    def __init__(
        self,
        parameters: dict[str, TaxParameter],
        sources: SourceRegistry | None = None,
    ) -> None:
        self._parameters = parameters
        self._sources = sources or SourceRegistry.load_default()

    @classmethod
    def load_default(cls) -> Self:
        """Load the bundled parameters.yaml registry."""
        raw = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any], sources: SourceRegistry | None = None) -> Self:
        """Build a registry from parsed YAML content (testing / external data)."""
        parameters: dict[str, TaxParameter] = {}
        for name, entry in (data.get("parameters") or {}).items():
            parameters[name] = TaxParameter(
                name=str(name),
                unit=str(entry.get("unit", "")),
                description=str(entry.get("description", "")),
                intervals=[_parse_interval(iv) for iv in entry.get("intervals", [])],
            )
        return cls(parameters, sources=sources)

    @property
    def sources(self) -> SourceRegistry:
        """The source registry backing this parameter registry."""
        return self._sources

    def names(self) -> list[str]:
        """All registered parameter names, sorted."""
        return sorted(self._parameters)

    def get(self, name: str) -> TaxParameter:
        """Fetch a parameter definition; raises UnknownParameterError when missing."""
        param = self._parameters.get(name)
        if param is None:
            raise UnknownParameterError(
                f"Unknown tax parameter: {name!r}. Known: {', '.join(self.names())}",
                code="UNKNOWN_PARAMETER",
            )
        return param

    def resolve(self, name: str, on_date: FiscalDate) -> ResolvedParameter:
        """Resolve a parameter for a Jalali/Gregorian date, with source provenance.

        Fail-closed:
        - unknown parameter -> UnknownParameterError
        - no covering interval -> ParameterNotEffectiveError
        - unknown source_id -> UnknownSourceError (from the registry)
        """
        param = self.get(name)
        interval = param.covering_interval(on_date)
        source = self._sources.get(interval.source_id)
        if source.verification_status not in (VerificationStatus.VERIFIED, VerificationStatus.CORROBORATED_CURRENT):
            raise HesabYarError(
                f"Parameter {name!r} interval source {interval.source_id!r} is "
                f"{source.verification_status.value}; not usable for answers.",
                code="SOURCE_NOT_USABLE",
            )
        return ResolvedParameter(
            name=param.name,
            value=interval.value,
            unit=param.unit,
            on_date=on_date.to_jalali_str(),
            effective_from=interval.effective_from,
            effective_to=interval.effective_to,
            source_id=source.source_id,
            verification_status=source.verification_status.value,
            note=interval.note,
        )

    def require_verified(self, name: str, on_date: FiscalDate) -> ResolvedParameter:
        """Resolve a parameter whose source MUST be VERIFIED (production submission path)."""
        resolved = self.resolve(name, on_date)
        self._sources.require_verified(resolved.source_id)
        return resolved


def _parse_interval(entry: dict[str, Any]) -> ParameterInterval:
    raw_value = entry["value"]
    if isinstance(raw_value, float):
        raise HesabYarError(
            f"Float parameter value is forbidden: {raw_value!r}. Use int or string-Decimal.",
            code="FLOAT_PARAMETER_FORBIDDEN",
        )
    value: Decimal | int
    if isinstance(raw_value, int):
        value = raw_value
    else:
        value = Decimal(str(raw_value))
    return ParameterInterval(
        value=value,
        effective_from=str(entry["effective_from"]),
        effective_to=entry.get("effective_to"),
        source_id=str(entry["source_id"]),
        note=str(entry.get("note", "")),
    )


__all__ = [
    "ParameterInterval",
    "ParameterNotEffectiveError",
    "ParameterRegistry",
    "ResolvedParameter",
    "TaxParameter",
    "UnknownParameterError",
]
