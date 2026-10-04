"""Tests for the migrated 40-rule catalog (rules.py) and the Moadian module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hesabyar.domain.standards.rules import RuleCatalog
from hesabyar.mcp.moadian import MoadianKB, validate_invoice

_SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "sample-data.json").read_text(encoding="utf-8"))


def _statements(**overrides: Any) -> dict[str, dict[str, Any]]:
    base = {
        "balance_sheet": dict(_SAMPLE["balance_sheet"]),
        "income_statement": dict(_SAMPLE["income_statement"]),
        "comprehensive_income": dict(_SAMPLE["comprehensive_income"]),
        "equity_changes": dict(_SAMPLE["equity_changes"]),
        "cash_flow": dict(_SAMPLE["cash_flow"], balance_sheet=_SAMPLE["balance_sheet"]),
    }
    base.update(overrides)
    return base


# =============================================================================
# Catalog integrity
# =============================================================================


class TestCatalogIntegrity:
    def test_forty_rules_migrated(self) -> None:
        catalog = RuleCatalog.default()
        assert len(catalog.all_rules()) == 40

    def test_legacy_ids_preserved(self) -> None:
        catalog = RuleCatalog.default()
        ids = {r.rule_id for r in catalog.all_rules()}
        assert {"BS001", "IS001", "CI001", "EC001", "CF001", "XC001", "MAT001"} <= ids
        assert {"BS-W01", "XC-W01"} <= ids

    def test_every_error_rule_has_message_and_refs(self) -> None:
        for rule in RuleCatalog.default().all_rules():
            if rule.message == "" and rule.severity.value == "error":
                pytest.fail(f"{rule.rule_id} is an error rule with no message")

    def test_formula_rules_have_expression(self) -> None:
        for rule in RuleCatalog.default().all_rules():
            if rule.requirement is None:
                assert rule.expression, f"{rule.rule_id} has neither expression nor requirement"


# =============================================================================
# Evaluation on the bundled sample
# =============================================================================


class TestSampleEvaluation:
    def test_sample_data_passes(self) -> None:
        catalog = RuleCatalog.default()
        evals = catalog.evaluate_all(_statements())
        failures = [
            (e.rule.rule_id, e.result.outcome.value, e.result.message)
            for e in evals
            if e.result.outcome.value in ("fail", "error") and e.result.severity.value == "error"
        ]
        assert failures == [], f"sample data should pass: {failures}"

    def test_not_applicable_is_never_pass_counted(self) -> None:
        catalog = RuleCatalog.default()
        evals = catalog.evaluate_all(_statements())
        na = [e for e in evals if e.result.outcome.value == "not_applicable"]
        assert na, "method-classified rules should be N/A for the nature-of-expense sample"
        assert all(e.result.outcome.value != "pass" or not e.rule.applies_to for e in na)

    def test_only_provided_categories_evaluated(self) -> None:
        catalog = RuleCatalog.default()
        evals = catalog.evaluate_all({"balance_sheet": _statements()["balance_sheet"]})
        assert all(e.rule.category in ("balance_sheet", "cross_checks") for e in evals)


# =============================================================================
# Fail-closed + explainability
# =============================================================================


class TestFailClosedAndExplain:
    def test_missing_field_is_error_never_pass(self) -> None:
        catalog = RuleCatalog.default()
        broken = {"balance_sheet": {"total_assets": 100}}  # nearly empty
        evals = catalog.evaluate_all(broken)
        outcomes = {e.rule.rule_id: e.result.outcome.value for e in evals if e.rule.category == "balance_sheet"}
        assert outcomes["BS001"] == "error"
        assert outcomes["BS002"] == "error"

    def test_unbalanced_balance_sheet_fails_with_explanation(self) -> None:
        catalog = RuleCatalog.default()
        data = _statements()
        data["balance_sheet"]["total_assets"] = 9_999_999  # break the identity
        evals = catalog.evaluate_all(data)
        bs001 = next(e for e in evals if e.rule.rule_id == "BS001")
        assert bs001.result.outcome.value == "fail"
        assert bs001.explanation is not None
        assert "1.55" in bs001.explanation  # standard ref present
        assert str(bs001.actual) in bs001.explanation  # substituted value present

    def test_explanation_includes_formula_and_refs(self) -> None:
        catalog = RuleCatalog.default()
        rule = catalog.get("BS001")
        ev = catalog.evaluate_rule(rule, {"total_assets": 10, "total_liabilities": 6, "total_equity": 5})
        assert ev.result.outcome.value == "fail"
        assert ev.explanation is not None
        assert "total_assets - (total_liabilities + total_equity)" in ev.explanation
        assert "استاندارد 1.55" in ev.explanation

    def test_cross_checks_merged_context(self) -> None:
        catalog = RuleCatalog.default()
        data = _statements()
        data["cash_flow"]["ending_cash"] = 999  # breaks CF003 and XC004
        evals = catalog.evaluate_all(data)
        failed_ids = {e.rule.rule_id for e in evals if e.result.outcome.value == "fail"}
        assert "CF003" in failed_ids
        assert "XC004" in failed_ids


# =============================================================================
# Moadian KB + offline invoice validator
# =============================================================================


_VALID_INVOICE: dict[str, Any] = {
    "header": {
        "inty": 1,
        "tins": "41134236658",
        "indatim": 1727000000000,
        "taxid": "41134236658140501",
        "crn": "14005567001",
        "tprdis": "1000000",
        "tdis": "0",
        "tadis": "1000000",
        "tvam": "90000",
        "todam": "0",
        "tbill": "1090000",
    },
    "body": [
        {
            "sstid": "2720000114542",
            "sstt": "خدمات نرم‌افزاری",
            "am": "1000000",
            "fee": "1000000",
            "ssrv": "1",
            "dis": "0",
            "vra": "0.09",
            "vam": "90000",
            "tsstam": "1090000",
        }
    ],
    "payment": [{"pny": 1, "acdn": "6037991712345678"}],
}


class TestMoadianKB:
    def test_kb_loads(self) -> None:
        kb = MoadianKB.default()
        assert len(kb.all_codes()) >= 15

    def test_known_code_explained(self) -> None:
        entry = MoadianKB.default().explain("4110")
        assert entry["found"] is True
        assert entry["cause"] and entry["resolution"]
        assert entry["verification_status"] in ("CORROBORATED_CURRENT", "DISCOVERY_ONLY")

    def test_unknown_code_is_honest(self) -> None:
        out = MoadianKB.default().explain("99999")
        assert out["found"] is False


class TestInvoiceValidator:
    def test_valid_b2b_invoice_passes(self) -> None:
        result = validate_invoice(_VALID_INVOICE)
        assert result["is_valid"], result["errors"]
        assert result["pattern"].startswith("نوع اول")

    def test_line_arithmetic_enforced(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        bad["body"][0]["am"] = "900000"  # fee×1 − 0 ≠ 900000
        result = validate_invoice(bad)
        assert not result["is_valid"]
        assert any(e["check"] == "body[0].am" for e in result["errors"])

    def test_vat_line_enforced(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        bad["body"][0]["vam"] = "10000"
        result = validate_invoice(bad)
        assert any(e["check"] == "body[0].vam" for e in result["errors"])

    def test_header_totals_enforced(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        bad["header"]["tbill"] = "123"
        result = validate_invoice(bad)
        assert any(e["check"] == "header.tbill" for e in result["errors"])

    def test_b2b_requires_buyer_id(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        del bad["header"]["crn"]
        result = validate_invoice(bad)
        assert any(e["check"] == "header.crn" for e in result["errors"])

    def test_invalid_pattern_rejected(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        bad["header"]["inty"] = 9
        result = validate_invoice(bad)
        assert any(e["check"] == "header.inty" for e in result["errors"])

    def test_taxid_length_checked(self) -> None:
        bad = json.loads(json.dumps(_VALID_INVOICE))
        bad["header"]["taxid"] = "12345"
        result = validate_invoice(bad)
        assert any(e["check"] == "header.taxid" for e in result["errors"])
