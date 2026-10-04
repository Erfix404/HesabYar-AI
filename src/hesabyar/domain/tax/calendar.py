"""Iranian tax-compliance calendar — Jalali deadlines and penalty estimation.

Deadline definitions follow the bundled Moadian/tax research
(docs/research_tax_inflation.md) and CURRENT_RULES_1405.md. Deadlines are
modeled as Jalali-anchored rules; exact dates resolve to FiscalDate. This module
answers "what is due next" and "what penalty applies if filed late" — it is
advisory and never implies taxability.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.errors import HesabYarError
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.tax.parameters import ParameterRegistry


class Obligation(StrEnum):
    """A recurring tax-filing obligation."""

    VAT_RETURN = "vat_return"  # اظهارنامه و پرداخت مالیات بر ارزش افزوده
    ARTICLE_169_QUARTERLY = "article_169_quarterly"  # صورت معاملات فصلی ماده ۱۶۹
    ANNUAL_RETURN = "annual_return"  # اظهارنامه عملکرد (شغل/شرکت)


class FilingStatus(StrEnum):
    """Filing position relative to the deadline."""

    ON_TIME = "on_time"
    LATE = "late"
    NOT_YET_DUE = "not_yet_due"


@dataclass(frozen=True)
class DeadlineRule:
    """A Jalali-anchored deadline rule for one obligation."""

    obligation: Obligation
    description: str
    penalty_rule: str
    source_id: str
    mode: str  # "months_after_year_end" | "days_after_quarter" | "jalali_fixed_day"

    # mode-specific fields
    month: int | None = None  # for jalali_fixed_day
    day: int | None = None
    days_after: int | None = None  # for days_after_quarter

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable rule."""
        return {
            "obligation": self.obligation.value,
            "description": self.description,
            "penalty_rule": self.penalty_rule,
            "source_id": self.source_id,
            "mode": self.mode,
            "month": self.month,
            "day": self.day,
            "days_after": self.days_after,
        }


@dataclass(frozen=True)
class UpcomingDeadline:
    """The next occurrence of an obligation on/after a reference date."""

    obligation: Obligation
    description: str
    due_date: FiscalDate
    days_remaining: int
    penalty_rule: str
    source_id: str
    verification_status: str
    period_label: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form."""
        return {
            "obligation": self.obligation.value,
            "description": self.description,
            "due_date_jalali": self.due_date.to_jalali_str(),
            "due_date_gregorian": self.due_date.to_gregorian_str(),
            "days_remaining": self.days_remaining,
            "penalty_rule": self.penalty_rule,
            "source_id": self.source_id,
            "verification_status": self.verification_status,
            "period_label": self.period_label,
            "note": self.note,
        }


@dataclass(frozen=True)
class PenaltyEstimate:
    """Deterministic penalty computation for a filing position."""

    obligation: Obligation
    status: FilingStatus
    days_late: int
    rate: str | None
    amount: MoneyIRR | None
    penalty_rule: str
    source_id: str
    verification_status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form."""
        return {
            "obligation": self.obligation.value,
            "status": self.status.value,
            "days_late": self.days_late,
            "rate": self.rate,
            "amount": str(self.amount.amount) if self.amount is not None else None,
            "penalty_rule": self.penalty_rule,
            "source_id": self.source_id,
            "verification_status": self.verification_status,
            "note": self.note,
        }


_QUARTER_NAMES = {1: "بهار", 2: "تابستان", 3: "پاییز", 4: "زمستان"}


class TaxCalendar:
    """Jalali tax-compliance calendar with deterministic penalty estimation."""

    def __init__(self, parameters: ParameterRegistry | None = None) -> None:
        self._parameters = parameters or ParameterRegistry.load_default()

    # -- rule table ---------------------------------------------------------

    @staticmethod
    def _rules() -> list[DeadlineRule]:
        """The bundled deadline rules (all Jalali-anchored, provenance-tracked)."""
        return [
            DeadlineRule(
                obligation=Obligation.VAT_RETURN,
                description="اظهارنامه و پرداخت مالیات بر ارزش افزوده هر دوره — تا ۱۵ روز پس از پایان دوره",
                penalty_rule="جریمه عدم تسلیم/تأخیر طبق ماده ۲۰ قانون ارزش افزوده (۱٪ عملکرد به‌ازای هر ماه تأخیر)",
                source_id="TAX-ADD-1400",
                mode="days_after_quarter",
                days_after=15,
            ),
            DeadlineRule(
                obligation=Obligation.ARTICLE_169_QUARTERLY,
                description="صورت معاملات فصلی ماده ۱۶۹ — حداکثر ۴۵ روز پس از پایان فصل",
                penalty_rule="جریمه ۱٪ مبلغ معاملات فصل (ماده ۱۹۹ ق.م.م) به‌ازای عدم تسلیم/تأخیر",
                source_id="TAX-QMM-CONSOLIDATED",
                mode="days_after_quarter",
                days_after=45,
            ),
            DeadlineRule(
                obligation=Obligation.ANNUAL_RETURN,
                description="اظهارنامه مالیاتی عملکرد اشخاص حقوقی — تا ۴ ماه پس از پایان سال مالی",
                penalty_rule="جریمه ۱٪ مالیات متعلق به‌ازای هر ماه تأخیر (حداکثر ۲۵٪)؛ ماده ۱۹۲ ق.م.م",
                source_id="TAX-QMM-CONSOLIDATED",
                mode="months_after_year_end",
            ),
            DeadlineRule(
                obligation=Obligation.ANNUAL_RETURN,
                description="اظهارنامه مالیاتی عملکرد مشاغل — تا پایان خرداد سال بعد",
                penalty_rule="جریمه ۱۰٪ درآمد مشمول (ماده ۱۹۲ ق.م.م — غیرقابل بخشودگی)",
                source_id="TAX-QMM-CONSOLIDATED",
                mode="jalali_fixed_day",
                month=3,
                day=31,
            ),
        ]

    # -- next deadlines -------------------------------------------------------

    def next_deadlines(self, on_date: FiscalDate, limit: int = 6) -> list[UpcomingDeadline]:
        """Return the next ``limit`` deadline occurrences on/after ``on_date``, sorted."""
        occurrences: list[UpcomingDeadline] = []
        for rule in self._rules():
            if rule.mode == "months_after_year_end":
                fy_end = self._jalali(on_date.jalali_year, 12, 29)
                due = self._add_jalali_months(fy_end, 4)
                if due.date < on_date.date:
                    fy_end = self._jalali(on_date.jalali_year + 1, 12, 29)
                    due = self._add_jalali_months(fy_end, 4)
                label = f"سال مالی {fy_end.jalali_year} (اشخاص حقوقی)"
                occurrences.append(self._build_upcoming(rule, due, on_date, label))
            elif rule.mode == "days_after_quarter":
                jy = on_date.jalali_year
                q = (on_date.jalali_month - 1) // 3 + 1
                # Candidates: previous, current, and next quarter deadlines —
                # the previous quarter's filing window can still be open.
                candidates: list[tuple[int, int, FiscalDate]] = []
                for qq, yy in ((q - 1, jy), (q, jy), (q + 1, jy)):
                    if qq == 0:
                        qq, yy = 4, jy - 1
                    elif qq == 5:
                        qq, yy = 1, jy + 1
                    q_end = self._quarter_end(yy, qq)
                    due = q_end + datetime.timedelta(days=int(rule.days_after or 0))
                    candidates.append((yy, qq, due))
                future = [c for c in candidates if c[2].date >= on_date.date]
                yy, qq, due = min(future) if future else min(candidates)
                label = f"فصل {_QUARTER_NAMES[qq]} {yy}"
                occurrences.append(self._build_upcoming(rule, due, on_date, label))
            elif rule.mode == "jalali_fixed_day":
                due = self._jalali(on_date.jalali_year, int(rule.month or 0), int(rule.day or 0))
                if due.date < on_date.date:
                    due = self._jalali(on_date.jalali_year + 1, int(rule.month or 0), int(rule.day or 0))
                label = f"عملکرد {due.jalali_year - 1} (مشاغل)"
                occurrences.append(self._build_upcoming(rule, due, on_date, label))
        occurrences.sort(key=lambda u: u.due_date.date)
        return occurrences[:limit]

    # -- penalty estimation -----------------------------------------------------

    def penalty_estimate(
        self,
        obligation: Obligation,
        due_date: FiscalDate,
        filed_on: FiscalDate,
        *,
        monthly_amount: MoneyIRR | None = None,
        taxable_amount: MoneyIRR | None = None,
    ) -> PenaltyEstimate:
        """Deterministically estimate the penalty for a filing position.

        - VAT / Article 169: 1% per (started) month of delay over the relevant amount.
        - Annual return (companies): 1% per (started) month of tax due, capped at 25%.
        - Annual return (businesses, خرداد ۳/۳۱ rule): flat 10% of assessable income.

        The annual-return rule shape is chosen by the *due-date form*: a Jalali
        3/31 due date selects the business rule; any other due date selects the
        4-months-after-year-end company rule.

        Raises:
            UnknownSourceError: if the rule's source_id is not registered.
        """
        rule = next((r for r in self._rules() if r.obligation == obligation), None)
        if rule is None:
            raise HesabYarError(f"No deadline rule for obligation {obligation!r}", code="UNKNOWN_OBLIGATION")
        status_value = self._sources.get(rule.source_id).verification_status.value

        days_late = (filed_on.date - due_date.date).days
        status = (
            FilingStatus.NOT_YET_DUE
            if days_late < 0
            else (FilingStatus.LATE if days_late > 0 else FilingStatus.ON_TIME)
        )

        if status != FilingStatus.LATE:
            return PenaltyEstimate(
                obligation=obligation,
                status=status,
                days_late=max(days_late, 0),
                rate=None,
                amount=None,
                penalty_rule=rule.penalty_rule,
                source_id=rule.source_id,
                verification_status=status_value,
                note="بدون جریمه تأخیر در این وضعیت",
            )

        months_late = days_late // 30 + (1 if days_late % 30 else 0)  # started-months convention
        is_business_annual = (
            obligation == Obligation.ANNUAL_RETURN
            and due_date.jalali_month == 3
            and due_date.jalali_day == 31
        )
        if is_business_annual:
            # مشاغل: جریمه مقطوع ۱۰٪ درآمد مشمول (ماده ۱۹۲ — غیرقابل بخشودگی)
            base = taxable_amount
            factor = Decimal("0.10")
            rate_str = "10% درآمد مشمول (ماده ۱۹۲ — مقطوع)"
        elif obligation == Obligation.ANNUAL_RETURN:
            # اشخاص حقوقی: ۱٪ مالیات به‌ازای هر ماه شروع‌شده، سقف ۲۵٪ (ماده ۱۹۲)
            base = monthly_amount
            factor = min(Decimal("0.01") * Decimal(months_late), Decimal("0.25"))
            rate_str = "۱٪ مالیات در ماه شروع‌شده، سقف ۲۵٪ (ماده ۱۹۲)"
        else:
            # ارزش افزوده / ماده ۱۶۹: ۱٪ به‌ازای هر ماه شروع‌شده
            base = monthly_amount
            factor = Decimal("0.01") * Decimal(months_late)
            rate_str = "۱٪ به‌ازای هر ماه شروع‌شده"

        if base is None:
            return PenaltyEstimate(
                obligation=obligation,
                status=status,
                days_late=days_late,
                rate=rate_str,
                amount=None,
                penalty_rule=rule.penalty_rule,
                source_id=rule.source_id,
                verification_status=status_value,
                note="مبلغ پایه ارائه نشد؛ فقط نرخ جریمه گزارش می‌شود",
            )

        amount = base.mul_decimal(factor)
        return PenaltyEstimate(
            obligation=obligation,
            status=status,
            days_late=days_late,
            rate=rate_str,
            amount=amount,
            penalty_rule=rule.penalty_rule,
            source_id=rule.source_id,
            verification_status=status_value,
            note=f"ضریب جریمه {factor} روی مبلغ پایه ({months_late} ماه شروع‌شده تأخیر)",
        )

    # -- helpers ---------------------------------------------------------------

    @property
    def _sources(self):  # noqa: ANN202 — narrow internal accessor
        """The source registry shared with the parameter registry."""
        return self._parameters.sources

    def _build_upcoming(
        self, rule: DeadlineRule, due: FiscalDate, on_date: FiscalDate, label: str
    ) -> UpcomingDeadline:
        return UpcomingDeadline(
            obligation=rule.obligation,
            description=rule.description,
            due_date=due,
            days_remaining=(due.date - on_date.date).days,
            penalty_rule=rule.penalty_rule,
            source_id=rule.source_id,
            verification_status=self._sources.get(rule.source_id).verification_status.value,
            period_label=label,
        )

    @staticmethod
    def _jalali(y: int, m: int, d: int) -> FiscalDate:
        return FiscalDate.from_jalali(y, m, d)

    @staticmethod
    def _is_jalali_leap(jy: int) -> bool:
        """33-year cycle Jalali leap test: year remainder in {1, 5, 9, 13, 17, 22, 26, 30}."""
        return jy % 33 in (1, 5, 9, 13, 17, 22, 26, 30)

    @classmethod
    def _quarter_end(cls, jy: int, q: int) -> FiscalDate:
        """Jalali quarter end: Q1..Q3 end 3/31, 6/31, 9/30; Q4 ends 12/29 (12/30 leap)."""
        if q < 4:
            end_day = 31 if q in (1, 2) else 30
            return FiscalDate.from_jalali(jy, q * 3, end_day)
        day = 30 if cls._is_jalali_leap(jy) else 29
        return FiscalDate.from_jalali(jy, 12, day)

    @classmethod
    def _add_jalali_months(cls, d: FiscalDate, months: int) -> FiscalDate:
        jd = d.jalali_date
        total = (jd.year * 12 + (jd.month - 1)) + months
        ny, nm0 = divmod(total, 12)
        nm = nm0 + 1
        day = jd.day
        if nm == 12:
            day = min(day, 30 if cls._is_jalali_leap(ny) else 29)
        elif nm >= 7:
            day = min(day, 30)
        return FiscalDate.from_jalali(ny, nm, day)


__all__ = [
    "DeadlineRule",
    "FilingStatus",
    "Obligation",
    "PenaltyEstimate",
    "TaxCalendar",
    "UpcomingDeadline",
]
