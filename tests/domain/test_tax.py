"""Tests for the Iranian tax-policy bounded context.

Covers: source registry provenance rules, effective-dated parameter resolution
(fail-closed), Article 6 calculator mechanics, and the Jalali tax calendar.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.errors import HesabYarError
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.tax.article6 import Article6Calculator
from hesabyar.domain.tax.calendar import Obligation, TaxCalendar
from hesabyar.domain.tax.parameters import (
    ParameterNotEffectiveError,
    ParameterRegistry,
    UnknownParameterError,
)
from hesabyar.domain.tax.sources import SourceRegistry, VerificationStatus

# =============================================================================
# Source registry
# =============================================================================


class TestSourceRegistry:
    def test_load_default_has_records(self) -> None:
        reg = SourceRegistry.load_default()
        assert len(reg.all_records()) >= 7
        ids = {r.source_id for r in reg.all_records()}
        assert "STD-43-REV-1404" in ids
        assert "TAX-POS-LAW-1398" in ids

    def test_get_unknown_raises(self) -> None:
        reg = SourceRegistry.load_default()
        with pytest.raises(HesabYarError, match="Unknown source_id"):
            reg.get("NOPE-123")

    def test_require_verified_fail_closed(self) -> None:
        reg = SourceRegistry.load_default()
        # TAX-QMM-CONSOLIDATED is CORROBORATED_CURRENT, not VERIFIED.
        with pytest.raises(HesabYarError, match="not VERIFIED"):
            reg.require_verified("TAX-QMM-CONSOLIDATED")
        # Bundled standards are VERIFIED.
        assert reg.require_verified("STD-43-REV-1404").source_id == "STD-43-REV-1404"

    def test_duplicate_ids_rejected(self) -> None:
        import copy

        reg = SourceRegistry.load_default()
        records = copy.deepcopy(reg.all_records())
        records.append(records[0])
        with pytest.raises(HesabYarError, match="Duplicate source_id"):
            SourceRegistry(records)

    def test_std15_is_retired(self) -> None:
        reg = SourceRegistry.load_default()
        rec = reg.get("STD-15-LEGACY-1380")
        assert rec.verification_status is VerificationStatus.RETIRED
        assert not rec.is_production_usable

    def test_provenance_echo(self) -> None:
        reg = SourceRegistry.load_default()
        echo = reg.provenance_echo("TAX-ADD-1400")
        assert echo["source_id"] == "TAX-ADD-1400"
        assert echo["verification_status"] == "CORROBORATED_CURRENT"


# =============================================================================
# Effective-dated parameters
# =============================================================================


class TestParameters:
    def test_vat_rate_by_period(self) -> None:
        reg = ParameterRegistry.load_default()
        assert reg.resolve("vat_rate", FiscalDate.from_jalali_str("1402/06/01")).value == Decimal("0.09")
        assert reg.resolve("vat_rate", FiscalDate.from_jalali_str("1403/06/01")).value == Decimal("0.10")
        assert reg.resolve("vat_rate", FiscalDate.from_jalali_str("1405/06/01")).value == Decimal("0.10")

    def test_article6_coefficient_change_date(self) -> None:
        reg = ParameterRegistry.load_default()
        before = reg.resolve("article_6_sales_cap_coefficient", FiscalDate.from_jalali_str("1402/08/23"))
        after = reg.resolve("article_6_sales_cap_coefficient", FiscalDate.from_jalali_str("1402/08/24"))
        assert int(before.value) == 3
        assert int(after.value) == 5

    def test_unknown_parameter_fails(self) -> None:
        reg = ParameterRegistry.load_default()
        with pytest.raises(UnknownParameterError):
            reg.resolve("nonexistent_param", FiscalDate.from_jalali_str("1405/01/01"))

    def test_gap_fails_closed(self) -> None:
        reg = ParameterRegistry.load_default()
        # article_84 starts 1405/01/01 — a date before must fail closed.
        with pytest.raises(ParameterNotEffectiveError):
            reg.resolve("article_84_annual_salary_exemption", FiscalDate.from_jalali_str("1404/06/01"))

    def test_float_value_rejected(self) -> None:
        with pytest.raises(HesabYarError, match="Float parameter"):
            ParameterRegistry.from_dict(
                {
                    "parameters": {
                        "x": {
                            "unit": "rate",
                            "intervals": [{"value": 0.1, "effective_from": "1400/01/01", "source_id": "TAX-ADD-1400"}],
                        }
                    }
                }
            )

    def test_provenance_carried(self) -> None:
        reg = ParameterRegistry.load_default()
        resolved = reg.resolve("article_101_annual_business_exemption", FiscalDate.from_jalali_str("1405/06/01"))
        assert resolved.value == 2_800_000_000
        assert resolved.source_id == "TAX-BUDGET-1405-PARAMS"
        assert resolved.verification_status == "CORROBORATED_CURRENT"

    def test_require_verified_rejects_corroborated(self) -> None:
        reg = ParameterRegistry.load_default()
        with pytest.raises(HesabYarError):
            reg.require_verified("article_101_annual_business_exemption", FiscalDate.from_jalali_str("1405/06/01"))


# =============================================================================
# Article 6 calculator
# =============================================================================


class TestArticle6:
    def test_initial_cap_prior_period_basis(self) -> None:
        calc = Article6Calculator()
        cap = calc.initial_cap(FiscalDate.from_jalali_str("1405/04/01"), MoneyIRR(2_800_000_000))
        assert cap.basis == "prior_period"  # exactly at the Article 101 exemption
        assert cap.coefficient == 5
        assert cap.initial_cap.amount == 14_000_000_000

    def test_initial_cap_article101_basis(self) -> None:
        calc = Article6Calculator()
        # Zero history → Article 101 basis (2,800,000,000 × 5).
        cap = calc.initial_cap(FiscalDate.from_jalali_str("1405/04/01"), MoneyIRR(0))
        assert cap.basis == "article_101"
        assert cap.initial_cap.amount == 14_000_000_000

    def test_article101_basis_when_below_exemption(self) -> None:
        calc = Article6Calculator()
        cap = calc.initial_cap(FiscalDate.from_jalali_str("1405/04/01"), MoneyIRR(2_799_999_999))
        assert cap.basis == "article_101"

    def test_cash_payment_lever_ten_x(self) -> None:
        calc = Article6Calculator()
        lever = calc.cash_payment_lever(FiscalDate.from_jalali_str("1405/06/01"), MoneyIRR(100_000_000))
        assert lever.unlocked_capacity.amount == 1_000_000_000  # 10x at 10% rate

    def test_cheque_rule_20_days(self) -> None:
        calc = Article6Calculator()
        ok = calc.cheque_eligibility(
            FiscalDate.from_jalali_str("1405/06/31"), FiscalDate.from_jalali_str("1405/07/20")
        )
        assert ok.eligible and ok.days_over == 0
        late = calc.cheque_eligibility(
            FiscalDate.from_jalali_str("1405/06/31"), FiscalDate.from_jalali_str("1405/07/25")
        )
        assert not late.eligible and late.days_over == 5

    def test_devolution_risk(self) -> None:
        calc = Article6Calculator()
        cap = calc.initial_cap(FiscalDate.from_jalali_str("1405/04/01"), MoneyIRR(2_800_000_000))
        safe = calc.devolution_risk(cap, MoneyIRR(14_000_000_000 - 1))
        assert not safe["breached"]
        over = calc.devolution_risk(cap, MoneyIRR(14_000_000_000 + 1))
        assert over["breached"] and over["buyer_vat_credit_at_risk"]


# =============================================================================
# Tax calendar
# =============================================================================


class TestTaxCalendar:
    def test_quarter_deadlines_include_current_window(self) -> None:
        cal = TaxCalendar()
        # Mid-summer 1405 (11/مرداد): the summer VAT deadline (15/مهر) is upcoming.
        upcoming = cal.next_deadlines(FiscalDate.from_jalali_str("1405/05/11"))
        vat = next(u for u in upcoming if u.obligation == Obligation.VAT_RETURN)
        assert vat.due_date.to_jalali_str() == "1405/07/15"

    def test_after_vat_deadline_next_quarter_window(self) -> None:
        cal = TaxCalendar()
        # 17/مهر: summer VAT (15/مهر) passed → next is autumn deadline.
        upcoming = cal.next_deadlines(FiscalDate.from_jalali_str("1405/07/17"))
        vat = next(u for u in upcoming if u.obligation == Obligation.VAT_RETURN)
        assert vat.due_date.to_jalali_str() == "1405/10/15"

    def test_article169_deadline_45_days(self) -> None:
        cal = TaxCalendar()
        # In mid-summer (11/مرداد) the spring (بهار) Art. 169 window is still open:
        # spring ends 1405/03/31 + 45 days → 1405/05/14.
        upcoming = cal.next_deadlines(FiscalDate.from_jalali_str("1405/05/11"))
        a169 = next(u for u in upcoming if u.obligation == Obligation.ARTICLE_169_QUARTERLY)
        assert a169.due_date.to_jalali_str() == "1405/05/14"
        assert a169.period_label.startswith("فصل بهار 1405")

    def test_jalali_leap_year_end(self) -> None:
        cal = TaxCalendar()
        # 1403 is a Jalali leap year → 12/30 valid.
        assert cal._quarter_end(1403, 4).to_jalali_str() == "1403/12/30"
        assert cal._quarter_end(1404, 4).to_jalali_str() == "1404/12/29"

    def test_penalty_one_percent_started_month(self) -> None:
        cal = TaxCalendar()
        est = cal.penalty_estimate(
            Obligation.ARTICLE_169_QUARTERLY,
            FiscalDate.from_jalali_str("1405/07/16"),
            FiscalDate.from_jalali_str("1405/08/20"),
            monthly_amount=MoneyIRR(10_000_000_000),
        )
        assert est.status.value == "late"
        assert est.amount is not None
        # 34 days late → 2 started months → 2% of 10,000,000,000 = 200,000,000.
        assert est.amount.amount == 200_000_000

    def test_penalty_company_annual_capped_at_25_percent(self) -> None:
        cal = TaxCalendar()
        # Companies: 4 months after fiscal year end 1404/12/29 → 1405/04/29.
        # Filed 10 months late (300 days) → 10% but capped at 25%... 10% < 25%,
        # so expect exactly 1% × 10 started months on 10B of tax due.
        est = cal.penalty_estimate(
            Obligation.ANNUAL_RETURN,
            FiscalDate.from_jalali_str("1405/04/29"),
            FiscalDate.from_jalali_str("1406/02/26"),
            monthly_amount=MoneyIRR(10_000_000_000),
        )
        assert est.status.value == "late"
        assert est.amount is not None
        # 300 days → 10 started months × 1% = 10% of 10,000,000,000.
        assert est.amount.amount == 1_000_000_000

    def test_penalty_company_cap_engages_beyond_25_months(self) -> None:
        cal = TaxCalendar()
        # Due 1405/04/29, filed 1408/06/10 ≈ 1160 days → 39 started months.
        # Uncapped would be 39%; the ماده ۱۹۲ cap is 25%.
        est = cal.penalty_estimate(
            Obligation.ANNUAL_RETURN,
            FiscalDate.from_jalali_str("1405/04/29"),
            FiscalDate.from_jalali_str("1408/06/10"),
            monthly_amount=MoneyIRR(10_000_000_000),
        )
        assert est.status.value == "late"
        assert est.amount is not None
        assert est.amount.amount == 2_500_000_000  # 25% of 10,000,000,000

    def test_penalty_business_annual_flat_ten_percent(self) -> None:
        cal = TaxCalendar()
        # Business (مشاغل) rule: due 3/31 → flat 10% of assessable income,
        # independent of delay length.
        est = cal.penalty_estimate(
            Obligation.ANNUAL_RETURN,
            FiscalDate.from_jalali_str("1405/03/31"),
            FiscalDate.from_jalali_str("1405/04/05"),
            taxable_amount=MoneyIRR(8_000_000_000),
        )
        assert est.status.value == "late"
        assert est.amount is not None
        assert est.amount.amount == 800_000_000

    def test_penalty_on_time_is_zero(self) -> None:
        cal = TaxCalendar()
        est = cal.penalty_estimate(
            Obligation.VAT_RETURN,
            FiscalDate.from_jalali_str("1405/07/15"),
            FiscalDate.from_jalali_str("1405/07/15"),
            monthly_amount=MoneyIRR(1_000_000_000),
        )
        assert est.status.value == "on_time"
        assert est.amount is None

    def test_penalty_not_yet_due(self) -> None:
        cal = TaxCalendar()
        est = cal.penalty_estimate(
            Obligation.VAT_RETURN,
            FiscalDate.from_jalali_str("1405/07/15"),
            FiscalDate.from_jalali_str("1405/07/01"),
        )
        assert est.status.value == "not_yet_due"

    def test_all_deadlines_carry_provenance(self) -> None:
        cal = TaxCalendar()
        for d in cal.next_deadlines(FiscalDate.from_jalali_str("1405/05/11")):
            assert d.source_id
            assert d.verification_status in ("VERIFIED", "CORROBORATED_CURRENT")
