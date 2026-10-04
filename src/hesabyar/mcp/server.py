"""HesabYar MCP server (stdio) — deterministic accounting tools for LLM agents.

Exposes the domain layer to Claude Code / Claude Desktop / any MCP client:

- validate_statements   — run the migrated 40-rule catalog over statement JSON
- validate_rule         — run one rule by id with explanation on failure
- search_standards      — search the 35-standard knowledge corpus
- get_standard          — fetch one standard's summary (SKILL.md body)
- check_tax_parameter   — resolve an effective-dated tax parameter (with provenance)
- calc_article6         — Article 6 sales-cap calculator
- tax_calendar_next     — upcoming Jalali tax deadlines
- penalty_estimate      — deterministic late-filing penalty estimate
- moadian_error         — explain a Moadian system error code
- validate_invoice      — offline e-invoice validation (Moadian patterns 1-7)

Design follows ARCHITECTURE.md: the LLM orchestrates; this server computes.
Every tool result carries source provenance where legal facts are involved.
Run:  uv run hesabyar-mcp   (or: uvx --from . hesabyar-mcp)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from hesabyar.domain.common.dates import FiscalDate
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.standards.rules import RuleCatalog
from hesabyar.domain.tax.article6 import Article6Calculator
from hesabyar.domain.tax.calendar import Obligation, TaxCalendar
from hesabyar.domain.tax.parameters import ParameterRegistry
from hesabyar.mcp.moadian import MoadianKB, validate_invoice

app = Server("hesabyar")

# ---------------------------------------------------------------- resources --

_STANDARDS_DIR = Path(__file__).resolve().parents[3] / "standards"


def _load_standard(skill_name: str) -> str | None:
    """Load a bundled per-standard SKILL.md body by directory name prefix."""
    if not _STANDARDS_DIR.is_dir():
        return None  # wheel install without the repo checkout — corpus not bundled
    for d in sorted(_STANDARDS_DIR.iterdir()):
        if d.is_dir() and d.name.startswith(f"{skill_name}-"):
            skill = d / "SKILL.md"
            if skill.exists():
                return skill.read_text(encoding="utf-8")
    return None


def _list_standards() -> list[dict[str, str]]:
    """List bundled standards with their SKILL.md frontmatter metadata."""
    if not _STANDARDS_DIR.is_dir():
        return []  # wheel install without the repo checkout — corpus not bundled
    out: list[dict[str, str]] = []
    for d in sorted(_STANDARDS_DIR.iterdir()):
        skill = d / "SKILL.md"
        if d.is_dir() and skill.exists():
            text = skill.read_text(encoding="utf-8")
            meta: dict[str, str] = {"directory": d.name}
            if text.startswith("---"):
                for line in text[3 : text.index("---", 3)].splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        meta[k.strip()] = v.strip()
            out.append(meta)
    return out


# -------------------------------------------------------------------- tools --

@app.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="validate_statements",
            description=(
                "اعتبارسنجی صورت‌های مالی ایران: ورودی JSON با کلیدهای balance_sheet, "
                "income_statement, comprehensive_income, equity_changes, cash_flow. "
                "خروجی: نتیجه ۴۰ قاعده DSL امن با توضیح فارسی خطاها."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "statements": {
                        "type": "object",
                        "description": "Statement JSON (same shape as tests/sample-data.json)",
                    },
                },
                "required": ["statements"],
            },
        ),
        Tool(
            name="validate_rule",
            description="اجرای یک قاعده مشخص (مثلاً BS001) روی داده‌ها با توضیح کامل در صورت خطا.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "statements": {"type": "object"},
                },
                "required": ["rule_id", "statements"],
            },
        ),
        Tool(
            name="search_standards",
            description="جستجو در فهرست ۳۵ استاندارد حسابداری ایران (نام، شماره، معادل IFRS).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text (title/number/IFRS code)"}
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_standard",
            description="دریافت چکیده اجرایی یک استاندارد بر اساس شماره (مثلاً '43') یا نام پوشه.",
            inputSchema={
                "type": "object",
                "properties": {
                    "standard": {"type": "string", "description": "Standard number or directory name"}
                },
                "required": ["standard"],
            },
        ),
        Tool(
            name="check_tax_parameter",
            description=(
                "استعلام پارامتر مالیاتی تاریخ‌دار (مثل vat_rate، article_101_annual_business_exemption) "
                "برای یک تاریخ شمسی، با ذکر منبع و وضعیت راستی‌آزمایی."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "on_date": {"type": "string", "description": "Jalali YYYY/MM/DD or ISO date"},
                },
                "required": ["name", "on_date"],
            },
        ),
        Tool(
            name="calc_article6",
            description=(
                "ماشین‌حساب ماده ۶ (حد مجاز فروش): سقف اولیه، اهرم پرداخت نقدی، "
                "شرایط چک صیادی، و ریسک عدول — با منبع."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "on_date": {"type": "string"},
                    "prior_period_taxable_sales": {"type": "integer", "description": "IRR"},
                    "issued_in_period": {"type": "integer", "description": "IRR — optional"},
                    "cash_payment": {"type": "integer", "description": "IRR — optional"},
                    "quarter_end": {"type": "string", "description": "Jalali — for cheque check"},
                    "cheque_due": {"type": "string", "description": "Jalali — for cheque check"},
                },
                "required": ["on_date", "prior_period_taxable_sales"],
            },
        ),
        Tool(
            name="tax_calendar_next",
            description="مهلت‌های پیشِ‌رو مالیاتی (ارزش افزوده، ماده ۱۶۹، اظهارنامه عملکرد) با تاریخ شمسی.",
            inputSchema={
                "type": "object",
                "properties": {
                    "on_date": {"type": "string"},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["on_date"],
            },
        ),
        Tool(
            name="penalty_estimate",
            description="برآورد قطعی جریمه تأخیر برای یک تکلیف مالیاتی (نرخ + مبلغ) با منبع.",
            inputSchema={
                "type": "object",
                "properties": {
                    "obligation": {
                        "type": "string",
                        "enum": ["vat_return", "article_169_quarterly", "annual_return"],
                    },
                    "due_date": {"type": "string"},
                    "filed_on": {"type": "string"},
                    "monthly_amount": {"type": "integer", "description": "IRR — base for 1%/month rules"},
                    "taxable_amount": {"type": "integer", "description": "IRR — base for flat 10% rule"},
                },
                "required": ["obligation", "due_date", "filed_on"],
            },
        ),
        Tool(
            name="moadian_error",
            description="توضیح خطای سامانه مؤدیان: کد خطا را بدهید، علت و راه‌حل فارسی برگردد.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Error code (e.g. '4110')"}
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="validate_invoice",
            description="اعتبارسنجی آفلاین صورتحساب الکترونیکی (الگوهای ۱ تا ۷ مؤدیان): ساختار، محاسبات، TaxID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice": {"type": "object", "description": "Invoice JSON (header/body/payment)"},
                },
                "required": ["invoice"],
            },
        ),
    ]


def _json_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@app.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        return _json_text(await _dispatch(name, arguments))
    except Exception as exc:  # noqa: BLE001 — tool boundary returns structured errors
        return _json_text({"error": str(exc), "code": getattr(exc, "code", type(exc).__name__)})


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "validate_statements":
        catalog = RuleCatalog.default()
        statements = args["statements"]
        cf = statements.get("cash_flow")
        if isinstance(cf, dict) and "balance_sheet" in statements:
            statements["cash_flow"] = dict(cf, balance_sheet=statements["balance_sheet"])
        evals = catalog.evaluate_all(statements)
        return {
            "summary": {
                "total": len(evals),
                "pass": sum(1 for e in evals if e.result.outcome.value == "pass"),
                "fail": sum(1 for e in evals if e.result.outcome.value == "fail"),
                "error": sum(1 for e in evals if e.result.outcome.value == "error"),
                "not_applicable": sum(1 for e in evals if e.result.outcome.value == "not_applicable"),
            },
            "results": [e.to_dict() for e in evals],
        }

    if name == "validate_rule":
        catalog = RuleCatalog.default()
        rule = catalog.get(args["rule_id"])
        category = rule.category
        statements = args["statements"]
        context = statements.get(category, statements)
        if category == "cross_checks":
            context = {k: v for k, v in statements.items() if isinstance(v, dict)}
        ev = catalog.evaluate_rule(rule, context)
        return ev.to_dict()

    if name == "search_standards":
        query = str(args.get("query", "")).lower()
        results = [
            meta
            for meta in _list_standards()
            if query in json.dumps(meta, ensure_ascii=False).lower()
        ]
        return {"count": len(results), "standards": results}

    if name == "get_standard":
        return {"content": _load_standard(str(args["standard"])) or f"Standard {args['standard']!r} not found"}

    if name == "check_tax_parameter":
        registry = ParameterRegistry.load_default()
        resolved = registry.resolve(args["name"], _parse_date_arg(args["on_date"]))
        return resolved.to_dict()

    if name == "calc_article6":
        calc = Article6Calculator()
        on = _parse_date_arg(args["on_date"])
        prior = MoneyIRR(int(args.get("prior_period_taxable_sales", 0)))
        if "quarter_end" in args and "cheque_due" in args:
            return calc.cheque_eligibility(
                _parse_date_arg(args["quarter_end"]), _parse_date_arg(args["cheque_due"])
            ).to_dict()
        if "cash_payment" in args:
            return calc.cash_payment_lever(on, MoneyIRR(int(args["cash_payment"]))).to_dict()
        cap = calc.initial_cap(on, prior)
        payload = cap.to_dict()
        if "issued_in_period" in args:
            payload["devolution_risk"] = calc.devolution_risk(cap, MoneyIRR(int(args["issued_in_period"])))
        return payload

    if name == "tax_calendar_next":
        cal = TaxCalendar()
        return [
            d.to_dict()
            for d in cal.next_deadlines(_parse_date_arg(args["on_date"]), limit=int(args.get("limit", 6)))
        ]

    if name == "penalty_estimate":
        cal = TaxCalendar()
        est = cal.penalty_estimate(
            Obligation(args["obligation"]),
            _parse_date_arg(args["due_date"]),
            _parse_date_arg(args["filed_on"]),
            monthly_amount=MoneyIRR(int(args["monthly_amount"])) if "monthly_amount" in args else None,
            taxable_amount=MoneyIRR(int(args["taxable_amount"])) if "taxable_amount" in args else None,
        )
        return est.to_dict()

    if name == "moadian_error":
        kb = MoadianKB.default()
        return kb.explain(str(args["code"]))

    if name == "validate_invoice":
        return validate_invoice(args["invoice"])

    raise ValueError(f"Unknown tool: {name}")


def _parse_date_arg(s: str) -> FiscalDate:
    """Parse a Jalali or ISO date argument."""
    if "/" in s:
        return FiscalDate.from_jalali_str(s)
    return FiscalDate.from_iso_str(s)


def main() -> None:
    """Run the MCP server over stdio."""
    import anyio

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    anyio.run(_run)


if __name__ == "__main__":
    main()
