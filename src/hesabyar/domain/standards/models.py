"""Domain models for the accounting standards validation bounded context.

Follows ARCHITECTURE.md §9: each rule carries severity, standard references,
and a closed result set (PASS | FAIL | NOT_APPLICABLE | ERROR).  An unknown
field or unevaluable formula MUST yield ERROR, never PASS.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum, unique
from typing import NewType

RuleId = NewType("RuleId", str)
"""Stable, human-readable rule identifier (e.g. 'BS001')."""

StandardCode = NewType("StandardCode", str)
"""Accounting standard number or code (e.g. 'IAS1', 'IACPA-01')."""


@unique
class RuleSeverity(StrEnum):
    """How a rule failure affects the overall validation report."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@unique
class RuleOutcome(StrEnum):
    """Result of evaluating a single rule against financial data.

    - PASS:           the rule's assertion held.
    - FAIL:           the rule's assertion did not hold.
    - NOT_APPLICABLE: the rule does not apply to the given data context.
    - ERROR:          the rule could not be evaluated (missing field, type error, etc.).
                      For mandatory rules, ERROR invalidates the entire report.
    """

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


@dataclass(frozen=True)
class StandardRevision:
    """A specific revision of an accounting standard."""

    standard_code: StandardCode
    title: str
    revision_id: str
    published_at: datetime.date | None = None
    effective_from: datetime.date | None = None
    effective_to: datetime.date | None = None
    status: str = "active"
    supersedes_revision_id: str | None = None


@dataclass(frozen=True)
class RuleResult:
    """The outcome of evaluating a single validation rule."""

    rule_id: RuleId
    outcome: RuleOutcome
    severity: RuleSeverity
    message: str = ""
    detail: str = ""

    @property
    def is_pass(self) -> bool:
        return self.outcome == RuleOutcome.PASS

    @property
    def is_failure(self) -> bool:
        return self.outcome in (RuleOutcome.FAIL, RuleOutcome.ERROR)


@dataclass
class ValidationReport:
    """Aggregated result of running all applicable rules against a dataset.

    Coverage counters follow ARCHITECTURE.md §9.5 — each category is reported
    separately so no misleading "N standards validated" claims can be made.
    """

    results: list[RuleResult] = field(default_factory=list)

    def add(self, result: RuleResult) -> None:
        self.results.append(result)

    @property
    def is_valid(self) -> bool:
        """A report is valid iff no ERROR-severity rule failed or errored."""
        return not any(
            r.severity == RuleSeverity.ERROR and r.outcome in (RuleOutcome.FAIL, RuleOutcome.ERROR)
            for r in self.results
        )

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.outcome == RuleOutcome.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.outcome == RuleOutcome.FAIL)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.outcome == RuleOutcome.ERROR)

    @property
    def not_applicable(self) -> int:
        return sum(1 for r in self.results if r.outcome == RuleOutcome.NOT_APPLICABLE)

    @property
    def total(self) -> int:
        return len(self.results)
