# ADR-0002: Reorient the repo as an offline MCP accounting agent

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The repository began as a corpus of Iranian accounting standards plus a legacy
YAML-rule validator (v1.0/1.1 lineage from `seiahposh/accounting-iran-standards`).
The 2026 roadmap considered three product shapes: a web dashboard, a Telegram
bot, and an MCP (Model Context Protocol) agent server. A web UI would duplicate
commercial accounting suites, and a Telegram bot would put unaudited tax
answers in front of non-experts. Meanwhile, the users with the strongest
fit — accountants and developers using Claude Code, Claude Desktop, Cursor and
other MCP clients — already have an orchestration layer that can call tools,
and the heaviest failure mode there (the LLM *guessing* legal numbers) is
exactly what legislation-as-code can prevent.

## Decision

1. **Product shape:** the repo ships a **stdio MCP server** (`hesabyar-mcp`)
   plus a small CLI (`hesabyar`) as the only user-facing surfaces. No web UI
   and no chat bot are planned; PRs adding them will be declined.
2. **Offline by construction:** every tool runs without network access. Moadian
   live submission (token/JWS/حافظه مالیاتی) is out of scope; the invoice
   validator is explicitly advisory. This keeps the security surface trivial
   and makes the agent safe to point at confidential ledgers.
3. **Agent ergonomics are a first-class deliverable:** `AGENTS.md`, a bundled
   Skill (`skills/hesabyar-accounting/`), `.mcp.json`, Docker artifacts and
   honest README language are part of the product, not documentation
   afterthoughts.
4. **Everything an agent reads is provenance-tracked:** parameters resolve
   only when an effective-dated interval with a registered source covers the
   date; unknown/ungated data fails closed. Golden eval cases
   (`tests/golden/cases.yaml`) freeze the tool layer's answers so regressions
   in legal computations surface as test failures, not silent drift.
5. The legacy corpus (standards/, validators/, templates/) remains as the
   knowledge substrate; its machine-readable rules were migrated into the
   deterministic DSL catalog with identical rule ids.

## Consequences

- Claude Code (or any MCP client) gets 10 deterministic tools on
  `uv run hesabyar-mcp` with zero setup beyond `uv sync`.
- The project cannot help with e-invoice *transmission*; users must pair it
  with an officially sanctioned SSPC solution for that step.
- Golden files must be regenerated deliberately (`scripts/gen_golden.py`)
  and reviewed against `docs/CURRENT_RULES_1405.md` — they are a contract,
  not an oracle.
- Documentation must stay honest about verification status
  (`CORROBORATED_CURRENT` ≠ official circular); this is enforced socially
  via review and technically by the fail-closed source registry.
