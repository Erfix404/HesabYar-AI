# AGENTS.md — HesabYar-AI

Instructions for AI coding agents (Claude Code, Cursor, Codex, Hermes, ...) working **on this repository's code**.
For accounting/tax **domain knowledge**, install the Skill in `skills/hesabyar-accounting/` instead.

## What this project is

HesabYar-AI is a deterministic Iranian accounting & tax-compliance engine designed to be
consumed by LLM agents:

1. **Domain tools** (`src/hesabyar/`) — exact Decimal/int arithmetic, effective-dated tax
   parameters, validation rules. The LLM is **never** the source of financial truth or arithmetic.
2. **Knowledge corpus** (`standards/`, `core/`, `templates/`, `mappings/`) — 35 Iranian
   accounting standards with per-standard `SKILL.md` summaries.
3. **Agent integration** — MCP server (`src/hesabyar/mcp/`), Agent Skill bundle (`skills/`),
   CLI (`src/hesabyar/cli.py`).

## Environment (Python 3.12 ONLY)

The project requires Python `>=3.12,<3.13`. Do **not** use the ambient system Python.
Always use `uv`:

```bash
uv sync --frozen          # install deps (dev group included)
uv run pytest -q          # run tests
uv run ruff check .       # lint
uv run pyright            # type check
uv run alembic upgrade head   # needs HESABYAR_DATABASE_URL (Postgres)
```

Tests that hit PostgreSQL are skipped/errored when no DB is reachable — that is
environmental, not a code failure. Local Postgres: `docker compose up -d postgres` then
`export HESABYAR_DATABASE_URL="postgresql+psycopg://hesabyar:hesabyar_pass@localhost:15445/hesabyar_test"`.

## Architecture authority

`docs/ARCHITECTURE.md` (HYA-A1-FINAL) is **normative**. If any file conflicts with it,
the architecture wins. Key non-negotiables:

- **Fail-closed**: unevaluable rule → `ERROR`, never `PASS`. `NOT_APPLICABLE` is never `PASS`.
- **No `eval`/`exec`/dynamic imports** for rule formulas. Use the closed DSL in
  `src/hesabyar/domain/standards/dsl.py`.
- **No float arithmetic** in financial code. `int` and `Decimal` only. `MoneyIRR` rejects floats.
- **Dates**: canonical storage is Gregorian; convert Jalali via `FiscalDate`
  (`hesabyar.domain.common.dates`). Never `datetime.now()` in domain logic — inject a `Clock`.
- **Tenant isolation**: business rows carry `tenant_id`; repositories must scope queries.
- **Legal/tax facts** need a `SourceRecord` with `verification_status=VERIFIED` before
  production logic may use them (`src/hesabyar/domain/tax/sources.py`). `CORROBORATED_CURRENT`
  values are usable only with an explicit provenance echo in output.

## Source-record data files

- `src/hesabyar/domain/tax/data/sources.yaml` — legal-source registry.
- `src/hesabyar/domain/tax/data/parameters.yaml` — effective-dated tax parameters.
- `src/hesabyar/mcp/data/moadian_errors.yaml` — Moadian error knowledge base.

When changing these YAML files: keep `verification_status` honest (`VERIFIED` only for
bundled/consolidated official text; `CORROBORATED_CURRENT` for multi-source current values),
and echo `source_id` + `verification_status` in any user-facing conclusion.

## Conventions

- Ruff: line-length 120, rules `E,F,W,I,UP`; `scripts/` excluded from lint.
- Pyright standard mode; public functions fully typed; `from __future__ import annotations`.
- Domain layer imports nothing from infrastructure. Adapters implement `ports.py` interfaces.
- Tests: pytest + hypothesis, `filterwarnings = error` is on — do not add warning suppressions.
- New DB tables need an Alembic migration (`migrations/versions/`, sequential IDs) and the
  CI roundtrip (`upgrade head → downgrade base → upgrade head`) must stay green.

## Commit style

Conventional commits (`feat(domain): ...`, `fix(tax): ...`) matching existing history.
Never commit without running `uv run pytest -q` and `uv run ruff check .` first.
