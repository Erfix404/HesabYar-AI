"""Generate the golden eval cases for the HesabYar MCP tool layer.

Runs every case through the real MCP dispatch function and freezes the full
output into tests/golden/cases.yaml. Review the generated expectations against
the law facts in docs/CURRENT_RULES_1405.md before committing — the golden file
is a regression contract, not a test oracle.

Run:  uv run python scripts/gen_golden.py
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hesabyar.mcp.server import _dispatch  # noqa: E402

_B2C_INVOICE = {
    "header": {
        "inty": 2, "tins": "41134236658", "indatim": 1727000000000,
        "tprdis": "500000", "tdis": "0", "tadis": "500000",
        "tvam": "45000", "todam": "0", "tbill": "545000",
    },
    "body": [{
        "sstid": "17100000000000000", "sstt": "کالا", "am": "500000",
        "fee": "500000", "ssrv": "1", "dis": "0", "vra": "0.09",
        "vam": "45000", "tsstam": "545000",
    }],
    "payment": [{"pny": 1}],
}


def _b2c_with(overrides: dict[str, Any]) -> dict[str, Any]:
    import copy

    inv = copy.deepcopy(_B2C_INVOICE)
    for dotted, value in overrides.items():
        section, key = dotted.split(".", 1)
        target = inv["body"][0] if section == "body" else inv[section]
        target[key] = value
    return inv


def _cases() -> list[dict[str, Any]]:
    sample = (Path(__file__).resolve().parents[1] / "tests" / "sample-data.json").read_text(encoding="utf-8")
    import json

    statements = json.loads(sample)

    return [
        # ---- validate_statements / validate_rule --------------------------
        {"id": "validate_statements_sample", "tool": "validate_statements",
         "args": {"statements": statements}},
        {"id": "validate_rule_bs001_fail", "tool": "validate_rule",
         "args": {"rule_id": "BS001",
                  "statements": {"balance_sheet": {"total_assets": 10, "total_liabilities": 6, "total_equity": 5}}}},
        {"id": "validate_rule_bs001_pass", "tool": "validate_rule",
         "args": {"rule_id": "BS001",
                  "statements": {"balance_sheet": {"total_assets": 11, "total_liabilities": 6, "total_equity": 5}}}},
        {"id": "validate_rule_cf002_fail", "tool": "validate_rule",
         "args": {"rule_id": "CF002",
                  "statements": {"cash_flow": {"beginning_cash": 400, "net_change_in_cash": 100,
                                               "effect_of_exchange_rate": 0, "ending_cash": 499}}}},
        {"id": "validate_rule_unknown_id", "tool": "validate_rule",
         "args": {"rule_id": "ZZ999", "statements": {}}},
        # ---- check_tax_parameter -----------------------------------------
        {"id": "vat_rate_1402", "tool": "check_tax_parameter",
         "args": {"name": "vat_rate", "on_date": "1402/06/01"}},
        {"id": "vat_rate_boundary_1402_12_29", "tool": "check_tax_parameter",
         "args": {"name": "vat_rate", "on_date": "1402/12/29"}},
        {"id": "vat_rate_boundary_1403_01_01", "tool": "check_tax_parameter",
         "args": {"name": "vat_rate", "on_date": "1403/01/01"}},
        {"id": "vat_rate_1405", "tool": "check_tax_parameter",
         "args": {"name": "vat_rate", "on_date": "1405/06/01"}},
        {"id": "article_84_1405", "tool": "check_tax_parameter",
         "args": {"name": "article_84_annual_salary_exemption", "on_date": "1405/03/01"}},
        {"id": "article_84_before_effective_error", "tool": "check_tax_parameter",
         "args": {"name": "article_84_annual_salary_exemption", "on_date": "1404/06/01"}},
        {"id": "article_101_1405", "tool": "check_tax_parameter",
         "args": {"name": "article_101_annual_business_exemption", "on_date": "1405/06/01"}},
        {"id": "article_100_1404", "tool": "check_tax_parameter",
         "args": {"name": "article_100_flat_tax_sales_ceiling", "on_date": "1404/09/01"}},
        {"id": "article_6_coeff_1402_08_23", "tool": "check_tax_parameter",
         "args": {"name": "article_6_sales_cap_coefficient", "on_date": "1402/08/23"}},
        {"id": "article_6_coeff_1402_08_24", "tool": "check_tax_parameter",
         "args": {"name": "article_6_sales_cap_coefficient", "on_date": "1402/08/24"}},
        {"id": "article_6_coeff_1399", "tool": "check_tax_parameter",
         "args": {"name": "article_6_sales_cap_coefficient", "on_date": "1399/05/01"}},
        {"id": "confirmation_window_1405", "tool": "check_tax_parameter",
         "args": {"name": "invoice_buyer_confirmation_window_days", "on_date": "1405/01/15"}},
        {"id": "unknown_parameter_error", "tool": "check_tax_parameter",
         "args": {"name": "nonexistent_param", "on_date": "1405/06/01"}},
        {"id": "parameter_bad_date_error", "tool": "check_tax_parameter",
         "args": {"name": "vat_rate", "on_date": "not-a-date"}},
        # ---- calc_article6 ------------------------------------------------
        {"id": "article6_cap_no_history", "tool": "calc_article6",
         "args": {"on_date": "1405/04/01", "prior_period_taxable_sales": 0}},
        {"id": "article6_cap_below_exemption", "tool": "calc_article6",
         "args": {"on_date": "1405/04/01", "prior_period_taxable_sales": 2_799_999_999}},
        {"id": "article6_cap_prior_basis", "tool": "calc_article6",
         "args": {"on_date": "1405/04/01", "prior_period_taxable_sales": 2_800_000_000}},
        {"id": "article6_cap_prior_basis_1402", "tool": "calc_article6",
         "args": {"on_date": "1402/08/23", "prior_period_taxable_sales": 1_000_000_000}},
        {"id": "article6_devolution_safe", "tool": "calc_article6",
         "args": {"on_date": "1405/04/01", "prior_period_taxable_sales": 2_800_000_000,
                  "issued_in_period": 13_999_999_999}},
        {"id": "article6_devolution_breach", "tool": "calc_article6",
         "args": {"on_date": "1405/04/01", "prior_period_taxable_sales": 2_800_000_000,
                  "issued_in_period": 14_000_000_001}},
        {"id": "article6_cash_lever", "tool": "calc_article6",
         "args": {"on_date": "1405/06/01", "prior_period_taxable_sales": 0, "cash_payment": 100_000_000}},
        {"id": "article6_cheque_ok", "tool": "calc_article6",
         "args": {"on_date": "1405/07/01", "prior_period_taxable_sales": 0,
                  "quarter_end": "1405/06/31", "cheque_due": "1405/07/20"}},
        {"id": "article6_cheque_late", "tool": "calc_article6",
         "args": {"on_date": "1405/07/01", "prior_period_taxable_sales": 0,
                  "quarter_end": "1405/06/31", "cheque_due": "1405/07/25"}},
        # ---- tax_calendar_next ---------------------------------------------
        {"id": "calendar_mid_summer_1405", "tool": "tax_calendar_next",
         "args": {"on_date": "1405/05/11"}},
        {"id": "calendar_after_vat_deadline", "tool": "tax_calendar_next",
         "args": {"on_date": "1405/07/17"}},
        {"id": "calendar_year_end_window", "tool": "tax_calendar_next",
         "args": {"on_date": "1405/12/20"}},
        {"id": "calendar_leap_year_end_1403", "tool": "tax_calendar_next",
         "args": {"on_date": "1403/12/25"}},
        # ---- penalty_estimate ----------------------------------------------
        {"id": "penalty_art169_34_days", "tool": "penalty_estimate",
         "args": {"obligation": "article_169_quarterly", "due_date": "1405/07/16",
                  "filed_on": "1405/08/20", "monthly_amount": 10_000_000_000}},
        {"id": "penalty_vat_on_time", "tool": "penalty_estimate",
         "args": {"obligation": "vat_return", "due_date": "1405/07/15",
                  "filed_on": "1405/07/15", "monthly_amount": 1_000_000_000}},
        {"id": "penalty_not_yet_due", "tool": "penalty_estimate",
         "args": {"obligation": "vat_return", "due_date": "1405/07/15",
                  "filed_on": "1405/07/01"}},
        {"id": "penalty_business_flat_10", "tool": "penalty_estimate",
         "args": {"obligation": "annual_return", "due_date": "1405/03/31",
                  "filed_on": "1405/04/05", "taxable_amount": 8_000_000_000}},
        {"id": "penalty_company_10_months", "tool": "penalty_estimate",
         "args": {"obligation": "annual_return", "due_date": "1405/04/29",
                  "filed_on": "1406/02/26", "monthly_amount": 10_000_000_000}},
        {"id": "penalty_company_cap_25", "tool": "penalty_estimate",
         "args": {"obligation": "annual_return", "due_date": "1405/04/29",
                  "filed_on": "1408/06/10", "monthly_amount": 10_000_000_000}},
        {"id": "penalty_no_base_rate_only", "tool": "penalty_estimate",
         "args": {"obligation": "article_169_quarterly", "due_date": "1405/07/16",
                  "filed_on": "1405/08/20"}},
        {"id": "penalty_unknown_obligation_error", "tool": "penalty_estimate",
         "args": {"obligation": "mystery", "due_date": "1405/07/16", "filed_on": "1405/08/20"}},
        # ---- moadian_error --------------------------------------------------
        {"id": "moadian_4110", "tool": "moadian_error", "args": {"code": "4110"}},
        {"id": "moadian_6115", "tool": "moadian_error", "args": {"code": "6115"}},
        {"id": "moadian_2330", "tool": "moadian_error", "args": {"code": "2330"}},
        {"id": "moadian_unknown_code", "tool": "moadian_error", "args": {"code": "9999"}},
        # ---- validate_invoice -----------------------------------------------
        {"id": "invoice_b2c_valid", "tool": "validate_invoice", "args": {"invoice": _B2C_INVOICE}},
        {"id": "invoice_b2b_missing_crn", "tool": "validate_invoice",
         "args": {"invoice": _b2c_with({"header.inty": 1})}},
        {"id": "invoice_vam_mismatch", "tool": "validate_invoice",
         "args": {"invoice": _b2c_with({"body.vam": "40000"})}},
        {"id": "invoice_tbill_mismatch", "tool": "validate_invoice",
         "args": {"invoice": _b2c_with({"header.tbill": "540000"})}},
        {"id": "invoice_missing_sstid", "tool": "validate_invoice",
         "args": {"invoice": _b2c_with({"body.sstid": ""})}},
        # ---- standards corpus ------------------------------------------------
        {"id": "search_standards_43", "tool": "search_standards", "args": {"query": "43"}},
        {"id": "search_standards_empty", "tool": "search_standards", "args": {"query": "zzzz-no-match"}},
        {"id": "get_standard_43", "tool": "get_standard", "args": {"standard": "43"}},
        {"id": "get_standard_missing", "tool": "get_standard", "args": {"standard": "9999"}},
        # ---- unknown tool ------------------------------------------------------
        {"id": "unknown_tool_error", "tool": "no_such_tool", "args": {}},
    ]


async def main() -> None:
    import yaml

    doc: dict[str, Any] = {
        "_comment": (
            "Golden eval cases for the HesabYar MCP tool layer. Frozen from "
            "scripts/gen_golden.py; every case runs through hesabyar.mcp.server._dispatch "
            "(the exact surface an MCP client hits). `expect` is a subset-match contract: "
            "dicts must contain the pinned keys with equal values; lists must have the same "
            "length with element-wise subset matches. Review expectations against "
            "docs/CURRENT_RULES_1405.md before regenerating."
        ),
        "cases": [],
    }
    for case in _cases():
        try:
            result = await _dispatch(case["tool"], case["args"])
        except Exception as exc:  # noqa: BLE001 — error cases are frozen too
            result = {"error": str(exc), "code": getattr(exc, "code", type(exc).__name__)}
        doc["cases"].append({"id": case["id"], "tool": case["tool"], "args": case["args"], "expect": result})
    out = Path(__file__).resolve().parents[1] / "tests" / "golden" / "cases.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"wrote {out} with {len(doc['cases'])} cases")


if __name__ == "__main__":
    asyncio.run(main())
