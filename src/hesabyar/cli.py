"""HesabYar CLI — deterministic hands for agents and scripts.

Commands:
    validate        Validate financial statements (JSON file) against the migrated rule catalog.
    param           Resolve an effective-dated tax parameter for a date.
    calc-article6   Compute the Article 6 initial sales cap / cash lever / cheque eligibility.
    calendar        Show upcoming tax deadlines (Jalali).

All outputs are structured JSON with source provenance, suitable for LLM agents.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.standards.rules import RuleCatalog
from hesabyar.domain.tax.article6 import Article6Calculator
from hesabyar.domain.tax.calendar import TaxCalendar
from hesabyar.domain.tax.parameters import ParameterRegistry


def _emit(payload: dict | list) -> None:
    """Print JSON to stdout (UTF-8, non-ASCII preserved when the stream allows it)."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        # Windows consoles with a legacy codepage (e.g. cp1256) cannot encode
        # Persian; fall back to ASCII-escaped JSON so output stays valid.
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def _parse_date(s: str) -> FiscalDate:
    """Parse a Jalali (YYYY/MM/DD) or Gregorian ISO date string."""
    if "/" in s:
        return FiscalDate.from_jalali_str(s)
    return FiscalDate.from_iso_str(s)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate statements from a JSON file against the migrated catalog."""
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    catalog = RuleCatalog.default()

    statements: dict = {}
    for key in ("balance_sheet", "income_statement", "comprehensive_income", "equity_changes", "cash_flow"):
        if key in data:
            statements[key] = data[key]
    if "cash_flow" in statements and "balance_sheet" in data:
        statements["cash_flow"] = dict(statements["cash_flow"], balance_sheet=data["balance_sheet"])

    evaluations = catalog.evaluate_all(statements)
    from collections import Counter

    counts = Counter(e.result.outcome.value for e in evaluations)
    payload = {
        "summary": {
            "total": len(evaluations),
            "pass": counts.get("pass", 0),
            "fail": counts.get("fail", 0),
            "error": counts.get("error", 0),
            "not_applicable": counts.get("not_applicable", 0),
            "is_valid": all(
                e.result.outcome.value not in ("fail", "error")
                for e in evaluations
                if e.result.severity.value == "error"
            ),
        },
        "results": [e.to_dict() for e in evaluations],
    }
    _emit(payload)
    return 0 if payload["summary"]["is_valid"] else 1


def cmd_param(args: argparse.Namespace) -> int:
    """Resolve a tax parameter for a date with provenance."""
    registry = ParameterRegistry.load_default()
    try:
        resolved = registry.resolve(args.name, _parse_date(args.on))
        _emit(resolved.to_dict())
        return 0
    except Exception as exc:  # noqa: BLE001 — CLI boundary reports errors as JSON
        _emit({"error": str(exc), "code": getattr(exc, "code", type(exc).__name__)})
        return 2


def cmd_calc_article6(args: argparse.Namespace) -> int:
    """Article 6 computations: cap / lever / cheque eligibility."""
    calc = Article6Calculator()
    on = _parse_date(args.on)

    if args.cheque_due:
        result = calc.cheque_eligibility(
            _parse_date(args.quarter_end), _parse_date(args.cheque_due)
        )
        _emit(result.to_dict())
        return 0

    if args.cash_payment is not None:
        lever = calc.cash_payment_lever(on, MoneyIRR(int(args.cash_payment)))
        _emit(lever.to_dict())
        return 0

    prior = MoneyIRR(int(args.prior_sales or 0))
    cap = calc.initial_cap(on, prior)
    payload = cap.to_dict()
    if args.issued is not None:
        payload["devolution_risk"] = calc.devolution_risk(cap, MoneyIRR(int(args.issued)))
    _emit(payload)
    return 0


def cmd_calendar(args: argparse.Namespace) -> int:
    """Upcoming tax deadlines."""
    cal = TaxCalendar()
    deadlines = cal.next_deadlines(_parse_date(args.on), limit=args.limit)
    _emit([d.to_dict() for d in deadlines])
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Assemble the CLI parser."""
    parser = argparse.ArgumentParser(prog="hesabyar", description="HesabYar-AI deterministic tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate financial statements (JSON)")
    p_val.add_argument("file", help="Path to statements JSON file")
    p_val.set_defaults(func=cmd_validate)

    p_param = sub.add_parser("param", help="Resolve an effective-dated tax parameter")
    p_param.add_argument("name", help="Parameter name (e.g. vat_rate)")
    p_param.add_argument("--on", required=True, help="Date (Jalali YYYY/MM/DD or ISO)")
    p_param.set_defaults(func=cmd_param)

    p_a6 = sub.add_parser("calc-article6", help="Article 6 sales-cap computations")
    p_a6.add_argument("--on", required=True, help="Reference date (Jalali YYYY/MM/DD or ISO)")
    p_a6.add_argument("--prior-sales", type=int, default=0, help="Prior-year same-period taxable sales (IRR)")
    p_a6.add_argument("--issued", type=int, default=None, help="Sales issued so far in period (IRR) → devolution risk")
    p_a6.add_argument("--cash-payment", type=int, default=None, help="Cash VAT payment (IRR) → unlocked capacity")
    p_a6.add_argument("--quarter-end", default=None, help="Quarter end (Jalali) for cheque check")
    p_a6.add_argument("--cheque-due", default=None, help="Cheque due date (Jalali) for cheque check")
    p_a6.set_defaults(func=cmd_calc_article6)

    p_cal = sub.add_parser("calendar", help="Upcoming tax deadlines")
    p_cal.add_argument("--on", required=True, help="Reference date (Jalali YYYY/MM/DD or ISO)")
    p_cal.add_argument("--limit", type=int, default=6)
    p_cal.set_defaults(func=cmd_calendar)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
