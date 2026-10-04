"""Article 6 sales-cap calculator — قانون پایانه‌های فروشگاهی و سامانه مؤدیان.

Deterministic mechanics per the bundled research (docs/research_tax_inflation.md §1)
and the effective-dated parameters registry:

- Initial cap = ``article_6_sales_cap_coefficient`` × (prior-year same-period
  taxable sales whose tax was paid/arranged), OR — for units without comparable
  history or with declared sales below the Article 101 exemption —
  coefficient × Article 101 annual exemption.
- Cash-payment lever: every Rial of cash VAT payment unlocks
  ``payment / vat_rate`` of sales capacity (10x leverage at the 10% rate).
- Cheque (صیادی) rule: cheque due date must fall within 20 days after the
  quarter end; otherwise the guarantee is not eligible.
- Devolution (عدول): issuing invoices beyond the cap blocks the buyer's VAT
  credit; a corrective reference invoice is required after raising the cap.

All arithmetic is exact (int/Decimal). Every result echoes source provenance.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.tax.parameters import ParameterRegistry

_CHEQUE_GRACE_DAYS = 20


@dataclass(frozen=True)
class Article6InitialCap:
    """The initial quarterly sales cap computed for one period."""

    coefficient: int
    basis: str  # "prior_period" | "article_101"
    prior_period_taxable_sales: MoneyIRR
    article_101_annual: MoneyIRR
    initial_cap: MoneyIRR
    on_date: str
    source_id: str
    verification_status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for MCP/CLI output."""
        return {
            "coefficient": self.coefficient,
            "basis": self.basis,
            "prior_period_taxable_sales": str(self.prior_period_taxable_sales.amount),
            "article_101_annual": str(self.article_101_annual.amount),
            "initial_cap": str(self.initial_cap.amount),
            "on_date": self.on_date,
            "source_id": self.source_id,
            "verification_status": self.verification_status,
            "note": self.note,
        }


@dataclass(frozen=True)
class ChequeEligibility:
    """Result of the صیادی cheque due-date eligibility check."""

    eligible: bool
    quarter_end: str
    cheque_due: str
    deadline: str
    days_over: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for MCP/CLI output."""
        return {
            "eligible": self.eligible,
            "quarter_end": self.quarter_end,
            "cheque_due": self.cheque_due,
            "deadline": self.deadline,
            "days_over": self.days_over,
            "note": self.note,
        }


@dataclass(frozen=True)
class CashPaymentLever:
    """Sales capacity unlocked by a cash VAT prepayment."""

    cash_payment: MoneyIRR
    vat_rate: str
    unlocked_capacity: MoneyIRR
    on_date: str
    source_id: str
    verification_status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for MCP/CLI output."""
        return {
            "cash_payment": str(self.cash_payment.amount),
            "vat_rate": self.vat_rate,
            "unlocked_capacity": str(self.unlocked_capacity.amount),
            "on_date": self.on_date,
            "source_id": self.source_id,
            "verification_status": self.verification_status,
            "note": self.note,
        }


class Article6Calculator:
    """Deterministic Article 6 computations backed by the parameter registry."""

    def __init__(self, parameters: ParameterRegistry | None = None) -> None:
        self._parameters = parameters or ParameterRegistry.load_default()

    # -- initial cap -------------------------------------------------------

    def initial_cap(
        self,
        on_date: FiscalDate,
        prior_period_taxable_sales: MoneyIRR,
    ) -> Article6InitialCap:
        """Compute the initial quarterly cap for the period containing ``on_date``.

        ``prior_period_taxable_sales`` is the corresponding prior-year period's
        taxable sales whose VAT was paid or arranged. When there is no history,
        or the prior-period declared sales are below the Article 101 annual
        exemption, the statutory Article 101 basis applies.
        """
        coeff = self._parameters.resolve("article_6_sales_cap_coefficient", on_date)
        art101 = self._parameters.resolve("article_101_annual_business_exemption", on_date)
        if coeff.unit != "multiplier" or art101.unit != "IRR":
            raise ValueError("Parameter unit mismatch for Article 6 computation.")
        coefficient = int(coeff.value)
        art101_money = MoneyIRR(int(art101.value))

        if prior_period_taxable_sales.is_zero or prior_period_taxable_sales.amount < art101_money.amount:
            basis = "article_101"
            cap = art101_money.mul_decimal(Decimal(coefficient))
            note = "واحد بدون سابقه/فروش کمتر از معافیت ماده ۱۰۱ — مبنای قانونی ماده ۱۰۱"
        else:
            basis = "prior_period"
            cap = prior_period_taxable_sales.mul_decimal(Decimal(coefficient))
            note = "مبنا: فروش مشمول دوره متناظر سال قبل که مالیات آن پرداخت یا ترتیب پرداخت آن داده شده"

        return Article6InitialCap(
            coefficient=coefficient,
            basis=basis,
            prior_period_taxable_sales=prior_period_taxable_sales,
            article_101_annual=art101_money,
            initial_cap=cap,
            on_date=on_date.to_jalali_str(),
            source_id=coeff.source_id,
            verification_status=coeff.verification_status,
            note=note,
        )

    # -- cash payment lever ------------------------------------------------

    def cash_payment_lever(self, on_date: FiscalDate, cash_payment: MoneyIRR) -> CashPaymentLever:
        """Capacity unlocked by a cash VAT prepayment: Δcap = payment / vat_rate."""
        vat = self._parameters.resolve("vat_rate", on_date)
        rate = vat.value if isinstance(vat.value, Decimal) else Decimal(vat.value)
        unlocked = cash_payment.mul_decimal(Decimal(1) / rate)
        return CashPaymentLever(
            cash_payment=cash_payment,
            vat_rate=str(rate),
            unlocked_capacity=unlocked,
            on_date=on_date.to_jalali_str(),
            source_id=vat.source_id,
            verification_status=vat.verification_status,
            note="هر ریال پرداخت نقدی مالیات، ظرفیت فروش به نسبت معکوس نرخ ارزش افزوده باز می‌کند",
        )

    # -- cheque eligibility --------------------------------------------------

    def cheque_eligibility(self, quarter_end: FiscalDate, cheque_due: FiscalDate) -> ChequeEligibility:
        """Check the صیادی-cheque 20-day rule: due date ≤ quarter_end + 20 days."""
        deadline = quarter_end + datetime.timedelta(days=_CHEQUE_GRACE_DAYS)
        days_over = (cheque_due.date - deadline.date).days
        eligible = days_over <= 0
        return ChequeEligibility(
            eligible=eligible,
            quarter_end=quarter_end.to_jalali_str(),
            cheque_due=cheque_due.to_jalali_str(),
            deadline=deadline.to_jalali_str(),
            days_over=max(days_over, 0),
            note=(
                "سررسید چک باید حداکثر ۲۰ روز پس از پایان فصل باشد"
                if eligible
                else "سررسید چک بیش از ۲۰ روز پس از پایان فصل است — این تضمین واجد شرایط افزایش سقف نیست"
            ),
        )

    # -- devolution (عدول) ---------------------------------------------------

    def devolution_risk(
        self,
        initial_cap: Article6InitialCap,
        issued_in_period: MoneyIRR,
    ) -> dict[str, Any]:
        """Assess whether issuing up to ``issued_in_period`` breaches the cap.

        Returns a structured, provenance-carrying assessment. This is advisory:
        it never implies taxability or a safe harbour.
        """
        over = issued_in_period.amount - initial_cap.initial_cap.amount
        breached = over > 0
        return {
            "breached": breached,
            "overage": str(MoneyIRR(max(over, 0)).amount),
            "initial_cap": str(initial_cap.initial_cap.amount),
            "issued_in_period": str(issued_in_period.amount),
            "buyer_vat_credit_at_risk": breached,
            "note": (
                "صدور فراتر از حد مجاز = عدول؛ اعتبار مالیاتی خریدار قطع می‌شود و "
                "پس از افزایش سقف، صورتحساب ارجاعی اصلاحی لازم است"
                if breached
                else "صدور در محدوده حد مجاز است"
            ),
            "source_id": initial_cap.source_id,
            "verification_status": initial_cap.verification_status,
        }


__all__ = [
    "Article6Calculator",
    "Article6InitialCap",
    "CashPaymentLever",
    "ChequeEligibility",
]
