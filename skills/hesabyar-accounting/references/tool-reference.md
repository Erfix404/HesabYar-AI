# HesabYar Tool Reference (for agents)

Complete reference for the deterministic tools exposed by the MCP server
(`hesabyar-mcp`) and the CLI (`hesabyar`). All outputs are JSON with provenance.

## CLI quick reference

```bash
uv run hesabyar validate path/to/statements.json       # 40-rule catalog
uv run hesabyar param vat_rate --on 1405/06/01          # "0.10" + source
uv run hesabyar calc-article6 --on 1405/04/01 --prior-sales 0
uv run hesabyar calc-article6 --on 1405/06/01 --cash-payment 100000000   # 10x lever
uv run hesabyar calc-article6 --on 1405/07/01 --quarter-end 1405/06/31 --cheque-due 1405/07/25
uv run hesabyar calendar --on 1405/07/11 --limit 6
```

Exit codes: `0` valid/ok, `1` validation failed, `2` usage/lookup error.

## MCP tools

### validate_statements
- **Input:** `{ statements: {...} }` — keys: balance_sheet, income_statement,
  comprehensive_income, equity_changes, cash_flow (same shape as `tests/sample-data.json`).
- **Behavior:** runs the migrated 40-rule catalog (DSL-safe, fail-closed). Only provided
  categories are evaluated; cross-checks always run with honest ERRORs for missing statements.
- **Output:** summary + per-rule results; failed rules include `explanation` (Persian,
  formula + actual value + standard refs).
- **Interpretation:** `error` outcome ≠ failure of the data — it means the rule COULD NOT
  be evaluated (missing field). Do not present it as PASS. `not_applicable` ≠ PASS.

### check_tax_parameter
- **Input:** `{ name, on_date }` — e.g. `vat_rate`, `article_101_annual_business_exemption`.
- **Fail-closed:** no covering interval for the date → error `PARAMETER_NOT_EFFECTIVE`.
  Never guess a year's value that isn't registered.

### calc_article6
- **Modes:** initial cap (needs on_date + prior_period_taxable_sales), cash lever
  (cash_payment), cheque eligibility (quarter_end + cheque_due), devolution risk
  (add issued_in_period).
- **Key facts encoded:** coefficient 5× since 1402/08/24 (3× before); Article 101 basis
  when no history; Δcap = payment / vat_rate; cheque due ≤ quarter_end + 20 days.

### tax_calendar_next / penalty_estimate
- Deadlines: VAT return +15d after quarter; ماده ۱۶۹ +45d; companies +4 months after
  year-end (ماده ۱۹۲: 1%/month, cap 25%); businesses till خرداد ۳۱ (flat 10% ماده ۱۹۲).
- Penalty math uses started-months convention with exact MoneyIRR arithmetic.

### moadian_error / validate_invoice
- KB codes: 1101-6132 (see `src/hesabyar/mcp/data/moadian_errors.yaml`).
- Invoice validation: structure (inty 1-7, tins 11-digit, taxid 17-digit), line math
  (am = fee×qty − dis; vam = am×vra), header totals (tadis = tprdis − tdis;
  tbill = tadis + tvam + todam), payment presence per pattern.

## Data files (registries)

| File | Purpose |
|---|---|
| `src/hesabyar/domain/tax/data/sources.yaml` | Legal-source registry (verification_status per record) |
| `src/hesabyar/domain/tax/data/parameters.yaml` | Effective-dated tax parameters |
| `src/hesabyar/mcp/data/moadian_errors.yaml` | Moadian error KB |

Adding a parameter interval without a registered source_id is rejected by the loader.
Adding a VERIFIED claim requires the text bundled in-repo (or a pinned snapshot + sha256).
