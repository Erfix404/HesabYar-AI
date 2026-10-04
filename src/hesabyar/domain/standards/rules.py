"""Typed catalog of migrated validation rules + explain-capable evaluation.

Migrates the 40 legacy rules (validators/rules.yaml) into closed typed DSL
expressions per docs/ARCHITECTURE.md §9.3. Every rule carries:

- a DSL arithmetic expression and a comparison form (expected/min/max/tolerance),
- standard references (refs) and the legacy rule id (provenance),
- severity and applicability context key (applies_to).

Evaluation is explain-capable: on FAIL or ERROR the caller can obtain the
formula with actual values substituted and the reference list, per the
explainability discipline (SKILL.md output rules; ARCHITECTURE.md §9.5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from hesabyar.domain.standards.dsl import evaluate_expression
from hesabyar.domain.standards.models import (
    RuleId,
    RuleOutcome,
    RuleResult,
    RuleSeverity,
)


@dataclass(frozen=True)
class Comparison:
    """How the DSL expression result is compared against a bound."""

    kind: str  # "expected" | "min" | "max"
    bound: str  # Decimal string
    tolerance: str = "0"

    def evaluate(self, actual: Decimal) -> bool:
        """Return True when the comparison holds."""
        bound = Decimal(self.bound)
        tol = Decimal(self.tolerance)
        if self.kind == "expected":
            return abs(actual - bound) <= tol
        if self.kind == "min":
            return actual >= bound
        return actual <= bound

    def describe(self) -> str:
        """Human-readable comparison description."""
        if self.kind == "expected":
            return f"باید برابر {self.bound} (با تحمل {self.tolerance}) باشد"
        if self.kind == "min":
            return f"باید ≥ {self.bound} باشد"
        return f"باید ≤ {self.bound} باشد"


@dataclass(frozen=True)
class MigratedRule:
    """A validation rule migrated to the closed typed DSL."""

    rule_id: str
    category: str
    description: str
    expression: str
    comparison: Comparison | None
    severity: RuleSeverity
    refs: list[str] = field(default_factory=list)
    applies_to: str | None = None
    requirement: str | None = None  # presence/truthiness check instead of formula
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable rule metadata (no evaluation)."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "description": self.description,
            "expression": self.expression,
            "comparison": None if self.comparison is None else vars(self.comparison),
            "severity": self.severity.value,
            "refs": self.refs,
            "applies_to": self.applies_to,
            "requirement": self.requirement,
            "message": self.message,
        }


@dataclass(frozen=True)
class RuleEvaluation:
    """The outcome of evaluating one migrated rule, with explanation material."""

    rule: MigratedRule
    result: RuleResult
    actual: Decimal | None
    explanation: str | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable outcome including explanation on failure."""
        payload: dict[str, Any] = {
            "rule_id": self.rule.rule_id,
            "outcome": self.result.outcome.value,
            "severity": self.result.severity.value,
            "message": self.result.message,
            "actual": None if self.actual is None else str(self.actual),
        }
        if self.explanation is not None:
            payload["explanation"] = self.explanation
        payload["refs"] = self.rule.refs
        return payload


class RuleCatalog:
    """The bundled catalog of migrated rules with evaluation and explanation."""

    def __init__(self, rules: list[MigratedRule]) -> None:
        self._rules = rules
        self._by_id = {r.rule_id: r for r in rules}

    @classmethod
    def default(cls) -> RuleCatalog:
        """Load the bundled migrated catalog (migrated from validators/rules.yaml)."""
        return cls(_build_catalog())

    def all_rules(self) -> list[MigratedRule]:
        """All catalog rules."""
        return list(self._rules)

    def by_category(self, category: str) -> list[MigratedRule]:
        """Rules of one statement category."""
        return [r for r in self._rules if r.category == category]

    def categories(self) -> list[str]:
        """Distinct categories in catalog order."""
        seen: list[str] = []
        for r in self._rules:
            if r.category not in seen:
                seen.append(r.category)
        return seen

    def get(self, rule_id: str) -> MigratedRule:
        """Fetch a rule by id; KeyError when missing."""
        return self._by_id[rule_id]

    # -- evaluation -----------------------------------------------------------

    def evaluate_rule(self, rule: MigratedRule, context: Mapping[str, Any]) -> RuleEvaluation:
        """Evaluate one rule against a context, fail-closed, with explanation."""
        if rule.applies_to is not None:
            method = context.get("classification_method") or context.get("method")
            if method != rule.applies_to:
                return RuleEvaluation(
                    rule=rule,
                    result=RuleResult(
                        rule_id=RuleId(rule.rule_id),
                        outcome=RuleOutcome.NOT_APPLICABLE,
                        severity=rule.severity,
                        message=f"Skipped (applies to {rule.applies_to})",
                    ),
                    actual=None,
                    explanation=None,
                )

        if rule.requirement is not None:
            value = context.get(rule.requirement)
            passed = bool(value)
            return RuleEvaluation(
                rule=rule,
                result=RuleResult(
                    rule_id=RuleId(rule.rule_id),
                    outcome=RuleOutcome.PASS if passed else RuleOutcome.FAIL,
                    severity=rule.severity,
                    message="" if passed else rule.message,
                ),
                actual=None,
                explanation=None if passed else self._explain_requirement(rule),
            )

        try:
            actual = evaluate_expression(rule.expression, context)
            if isinstance(actual, bool):
                raise ValueError("Expression must evaluate to a numeric value, not boolean")
            if not isinstance(actual, Decimal):
                actual = Decimal(actual)
        except Exception as exc:  # fail-closed: any evaluation error is ERROR
            return RuleEvaluation(
                rule=rule,
                result=RuleResult(
                    rule_id=RuleId(rule.rule_id),
                    outcome=RuleOutcome.ERROR,
                    severity=rule.severity,
                    message=f"Rule evaluation error: {exc}",
                ),
                actual=None,
                explanation=self._explain_error(rule, exc),
            )

        if rule.comparison is None:
            # No comparison bound: expression itself is the assertion (boolean coerced numeric).
            outcome = RuleOutcome.PASS if actual == 0 else RuleOutcome.FAIL
        else:
            outcome = RuleOutcome.PASS if rule.comparison.evaluate(actual) else RuleOutcome.FAIL

        explanation = None
        if outcome is RuleOutcome.FAIL:
            explanation = self._explain_fail(rule, actual)
        return RuleEvaluation(
            rule=rule,
            result=RuleResult(
                rule_id=RuleId(rule.rule_id),
                outcome=outcome,
                severity=rule.severity,
                message="" if outcome is RuleOutcome.PASS else rule.message.format(
                    diff=actual, value=actual
                ),
            ),
            actual=actual,
            explanation=explanation,
        )

    def evaluate_category(self, category: str, context: Mapping[str, Any]) -> list[RuleEvaluation]:
        """Evaluate all rules of a category against a context."""
        return [self.evaluate_rule(r, context) for r in self.by_category(category)]

    def evaluate_all(self, statements: Mapping[str, Mapping[str, Any]]) -> list[RuleEvaluation]:
        """Evaluate provided statement categories against their contexts.

        ``statements`` keys mirror the legacy file: balance_sheet, income_statement,
        comprehensive_income, equity_changes, cash_flow, materiality.
        Only provided categories are evaluated — per-item rules (e.g. materiality,
        which need an ``amount`` field) are skipped unless their context is given.
        Cross-checks always run against a merged context of all provided statements;
        missing statements surface as honest ERROR results (fail-closed).
        """
        evaluations: list[RuleEvaluation] = []
        merged: dict[str, Any] = {}
        for category in self.categories():
            if category == "cross_checks":
                continue
            if category not in statements:
                continue
            context = statements[category]
            evaluations.extend(self.evaluate_category(category, context))
            merged[category] = context
        evaluations.extend(self.evaluate_category("cross_checks", merged))
        return evaluations

    # -- explanation builders ---------------------------------------------------

    def _explain_fail(self, rule: MigratedRule, actual: Decimal) -> str:
        bound_desc = rule.comparison.describe() if rule.comparison else "باید صفر باشد"
        refs = ", ".join(f"استاندارد {r}" for r in rule.refs) if rule.refs else "بدون ارجاع ثبت‌شده"
        return (
            f"فرمول: {rule.expression} = {actual} — {bound_desc}. "
            f"مقدار به‌دست‌آمده {actual} است. مرجع: {refs}"
        )

    def _explain_error(self, rule: MigratedRule, exc: Exception) -> str:
        refs = ", ".join(f"استاندارد {r}" for r in rule.refs) if rule.refs else "بدون ارجاع ثبت‌شده"
        return (
            f"ارزیابی قاعده ممکن نشد ({type(exc).__name__}: {exc}). "
            "نتیجه به‌جای حدس، ERROR است (fail-closed). مرجع: " + refs
        )

    def _explain_requirement(self, rule: MigratedRule) -> str:
        return (
            f"فیلد الزامی «{rule.requirement}» در داده‌ها یافت نشد یا نادرست (falsy) است. "
            f"پیام قاعده: {rule.message}"
        )


def _cmp(expected: str = "0", tolerance: str = "0.01", kind: str = "expected") -> Comparison:
    return Comparison(kind=kind, bound=expected, tolerance=tolerance)


def _build_catalog() -> list[MigratedRule]:
    """The 40 migrated rules — provenance: validators/rules.yaml (legacy ids kept)."""
    rules: list[MigratedRule] = []

    # ---------------- balance sheet (11) ----------------
    rules += [
        MigratedRule(
            rule_id="BS001", category="balance_sheet", description="معادله اصلی حسابداری",
            expression="total_assets - (total_liabilities + total_equity)", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.55"],
            message="ترازنامه تراز نیست (اختلاف: {diff})",
        ),
        MigratedRule(
            rule_id="BS002", category="balance_sheet", description="تفکیک دارایی‌ها",
            expression="(total_current_assets + total_non_current_assets) - total_assets",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.62"],
            message="جمع دارایی جاری و غیرجاری با کل دارایی مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS003", category="balance_sheet", description="تفکیک بدهی‌ها",
            expression="(total_current_liabilities + total_non_current_liabilities) - total_liabilities",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.62"],
            message="جمع بدهی جاری و غیرجاری با کل بدهی مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS004", category="balance_sheet", description="جمع اجزای دارایی جاری",
            expression="sum(current_assets_items) - total_current_assets", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.68"],
            message="جمع اجزای دارایی جاری مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS005", category="balance_sheet", description="جمع اجزای دارایی غیرجاری",
            expression="sum(non_current_assets_items) - total_non_current_assets", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.55"],
            message="جمع اجزای دارایی غیرجاری مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS006", category="balance_sheet", description="جمع اجزای بدهی جاری",
            expression="sum(current_liabilities_items) - total_current_liabilities", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.69"],
            message="جمع اجزای بدهی جاری مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS007", category="balance_sheet", description="جمع اجزای بدهی غیرجاری",
            expression="sum(non_current_liabilities_items) - total_non_current_liabilities",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.69"],
            message="جمع اجزای بدهی غیرجاری مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS008", category="balance_sheet", description="جمع اجزای حقوق مالکانه",
            expression="sum(equity_items) - total_equity", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.108"],
            message="جمع اجزای حقوق مالکانه مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="BS-W01", category="balance_sheet", description="نسبت جاری",
            expression="total_current_assets / total_current_liabilities",
            comparison=_cmp(expected="1.0", kind="min"), severity=RuleSeverity.WARNING,
            refs=[], message="نسبت جاری کمتر از ۱ (مقدار: {value})",
        ),
        MigratedRule(
            rule_id="BS-W02", category="balance_sheet", description="نسبت بدهی به حقوق مالکانه",
            expression="total_liabilities / total_equity",
            comparison=_cmp(expected="2.0", kind="max"), severity=RuleSeverity.WARNING,
            refs=[], message="نسبت بدهی به حقوق مالکانه بالاست (مقدار: {value})",
        ),
        MigratedRule(
            rule_id="BS-W03", category="balance_sheet", description="نسبت بدهی",
            expression="total_liabilities / total_assets",
            comparison=_cmp(expected="0.7", kind="max"), severity=RuleSeverity.WARNING,
            refs=[], message="نسبت بدهی بالاست (مقدار: {value})",
        ),
    ]

    # ---------------- income statement (7) ----------------
    rules += [
        MigratedRule(
            rule_id="IS001", category="income_statement", description="جمع هزینه‌ها (روش ماهیت)",
            expression=(
                "(raw_materials_consumed + employee_benefits + depreciation + other_expenses "
                "- changes_in_inventory) - total_expenses"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.96"],
            applies_to="nature_of_expense", message="جمع هزینه‌ها مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS002", category="income_statement", description="سود عملیاتی (روش ماهیت)",
            expression="(revenue + other_income - total_expenses) - operating_profit",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.96"],
            applies_to="nature_of_expense", message="سود عملیاتی مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS003", category="income_statement", description="سود ناخالص (روش کارکرد)",
            expression="(revenue - cost_of_goods_sold) - gross_profit", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.97"],
            applies_to="function_of_expense", message="سود ناخالص مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS004", category="income_statement", description="سود عملیاتی (روش کارکرد)",
            expression=(
                "(gross_profit + other_income - selling_expenses - administrative_expenses "
                "- other_expenses) - operating_profit"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.97"],
            applies_to="function_of_expense", message="سود عملیاتی مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS005", category="income_statement", description="سود قبل از مالیات",
            expression="(operating_profit - finance_costs + share_of_associates) - profit_before_tax",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.83"],
            message="سود قبل از مالیات مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS006", category="income_statement", description="سود خالص",
            expression="(profit_before_tax - tax_expense + discontinued_operations) - net_profit",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.83"],
            message="سود خالص مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="IS007", category="income_statement", description="تفکیک سود خالص",
            expression="(owners_of_parent + non_controlling_interests) - net_profit",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.83"],
            message="تفکیک سود خالص مطابقت ندارد",
        ),
    ]

    # ---------------- comprehensive income (3) ----------------
    rules += [
        MigratedRule(
            rule_id="CI001", category="comprehensive_income", description="مجموع سود و زیان جامع",
            expression="(net_profit + subtotal_not_reclassified + subtotal_reclassified) - total_comprehensive_income",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.100"],
            message="مجموع سود و زیان جامع مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CI002", category="comprehensive_income", description="تفکیک مجموع سود و زیان جامع",
            expression="(owners_of_parent + non_controlling_interests) - total_comprehensive_income",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.100"],
            message="تفکیک مجموع سود و زیان جامع مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CI003", category="comprehensive_income", description="اقلام غیرقابل انتقال",
            expression="reclassification_adjustments", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["1.101"], applies_to="items_not_reclassified",
            message="اقلام گروه «غیرقابل انتقال» نباید تعدیل تجدید طبقه‌بندی داشته باشند",
        ),
    ]

    # ---------------- equity changes (4) ----------------
    rules += [
        MigratedRule(
            rule_id="EC001", category="equity_changes", description="معادله اصلی حقوق مالکانه",
            expression=(
                "(adjusted_opening_balance + total_comprehensive_income + total_owner_transactions) "
                "- closing_balance.total_equity"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.108"],
            message="معادله اصلی حقوق مالکانه مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="EC002", category="equity_changes", description="مانده تعدیل‌شده ابتدای دوره",
            expression=(
                "(opening_balance + retrospective_application + retrospective_restatement) "
                "- adjusted_opening_balance"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.108"],
            message="مانده تعدیل‌شده ابتدای دوره مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="EC003", category="equity_changes", description="مجموع سود و زیان جامع",
            expression="(net_profit + other_comprehensive_income) - total_comprehensive_income",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.108"],
            message="مجموع سود و زیان جامع مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="EC004", category="equity_changes", description="جمع معاملات با مالکان",
            expression=(
                "(capital_contributions - distributions_to_owners + changes_in_ownership) "
                "- total_owner_transactions"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["1.108"],
            message="جمع معاملات با مالکان مطابقت ندارد",
        ),
    ]

    # ---------------- cash flow (5) ----------------
    rules += [
        MigratedRule(
            rule_id="CF001", category="cash_flow", description="تغییر خالص در نقد",
            expression=(
                "(net_cash_from_operating + net_cash_from_investing + net_cash_from_financing) "
                "- net_change_in_cash"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["2"],
            message="تغییر خالص در نقد مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CF002", category="cash_flow", description="مانده پایان",
            expression="(beginning_cash + net_change_in_cash + effect_of_exchange_rate) - ending_cash",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["2"],
            message="مانده پایان مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CF003", category="cash_flow", description="مطابقت با ترازنامه",
            expression="ending_cash - balance_sheet.cash_and_equivalents", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=["2"],
            message="مانده پایان با ترازنامه مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CF004", category="cash_flow", description="جریان عملیاتی (روش غیرمستقیم)",
            expression=(
                "(net_profit_before_tax + depreciation + amortization + provisions + impairment_losses "
                "+ foreign_exchange_gains_losses + gains_losses_on_disposal + change_in_receivables "
                "+ change_in_inventory + change_in_payables + change_in_other_working_capital "
                "- income_tax_paid + other_adjustments) - net_cash_from_operating"
            ),
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=["2"],
            applies_to="indirect", message="جریان عملیاتی (روش غیرمستقیم) مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="CF005", category="cash_flow", description="معاملات غیرنقدی",
            expression="", comparison=None, severity=RuleSeverity.ERROR, refs=["2"],
            requirement="non_cash_transactions_disclosed",
            message="معاملات غیرنقدی بااهمیت باید افشا شوند",
        ),
    ]

    # ---------------- cross checks (6) ----------------
    rules += [
        MigratedRule(
            rule_id="XC001", category="cross_checks", description="مطابقت سود خالص",
            expression="income_statement.net_profit - equity_changes.net_profit", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=[],
            message="سود خالص در صورت سود و زیان و تغییرات حقوق مالکانه مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="XC002", category="cross_checks", description="مطابقت سایر اقلام OCI",
            expression="comprehensive_income.other_comprehensive_income - equity_changes.other_comprehensive_income",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=[],
            message="سایر اقلام OCI مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="XC003", category="cross_checks", description="مطابقت مجموع سود و زیان جامع",
            expression="comprehensive_income.total_comprehensive_income - equity_changes.total_comprehensive_income",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=[],
            message="مجموع سود و زیان جامع مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="XC004", category="cross_checks", description="مطابقت نقد و معادل‌های نقد",
            expression="cash_flow.ending_cash - balance_sheet.cash_and_equivalents", comparison=_cmp(),
            severity=RuleSeverity.ERROR, refs=[],
            message="نقد و معادل‌های نقد مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="XC005", category="cross_checks", description="مطابقت حقوق مالکانه",
            expression="balance_sheet.total_equity - equity_changes.closing_balance.total_equity",
            comparison=_cmp(), severity=RuleSeverity.ERROR, refs=[],
            message="مجموع حقوق مالکانه مطابقت ندارد",
        ),
        MigratedRule(
            rule_id="XC-W01", category="cross_checks", description="مطابقت استهلاک",
            expression="income_statement.depreciation - cash_flow.depreciation", comparison=_cmp(),
            severity=RuleSeverity.WARNING, refs=[],
            message="استهلاک در صورت سود و زیان و جریان نقدی مطابقت ندارد",
        ),
    ]

    # ---------------- materiality (4, informational) ----------------
    rules += [
        MigratedRule(
            rule_id="MAT001", category="materiality", description="اهمیت نسبت به سود قبل از مالیات",
            expression="amount / profit_before_tax",
            comparison=_cmp(expected="0.05", kind="max"), severity=RuleSeverity.INFO, refs=[],
            message="قلم بااهمیت نسبت به سود",
        ),
        MigratedRule(
            rule_id="MAT002", category="materiality", description="اهمیت نسبت به کل دارایی‌ها",
            expression="amount / total_assets",
            comparison=_cmp(expected="0.01", kind="max"), severity=RuleSeverity.INFO, refs=[],
            message="قلم بااهمیت نسبت به دارایی‌ها",
        ),
        MigratedRule(
            rule_id="MAT003", category="materiality", description="اهمیت نسبت به درآمد عملیاتی",
            expression="amount / revenue",
            comparison=_cmp(expected="0.005", kind="max"), severity=RuleSeverity.INFO, refs=[],
            message="قلم بااهمیت نسبت به درآمد",
        ),
        MigratedRule(
            rule_id="MAT004", category="materiality", description="اهمیت نسبت به حقوق مالکانه",
            expression="amount / total_equity",
            comparison=_cmp(expected="0.02", kind="max"), severity=RuleSeverity.INFO, refs=[],
            message="قلم بااهمیت نسبت به حقوق مالکانه",
        ),
    ]

    return rules


__all__ = [
    "Comparison",
    "MigratedRule",
    "RuleCatalog",
    "RuleEvaluation",
]
