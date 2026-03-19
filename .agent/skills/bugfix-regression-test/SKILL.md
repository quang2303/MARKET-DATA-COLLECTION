---
name: bugfix-regression-test
description: Use this skill when debugging or fixing a bug in the market-data backend. Especially for FastAPI endpoints, database query issues, asyncpg problems, fetcher bugs, or incorrect business logic. This skill enforces root-cause analysis, minimal patching, and regression testing.
---

# Bugfix Regression Test Skill

## Goal
Fix bugs safely in this repository by following a strict workflow:
reproduce -> isolate root cause -> minimal patch -> regression test -> verify.

## Repository Context
- Main layers:
  - `api/` = FastAPI app and routers
  - `core/` = shared Pydantic models and schemas
  - `db/` = TimescaleDB and asyncpg access
  - `fetchers/` = market data ingestion logic
- Shared contracts must use models from `core/models.py`.
- Do not pass raw dicts across layers unless the existing code already forces it.
- Read `pyproject.toml` and `CONTRIBUTING.md` before changing code.

## Instructions
1. Reproduce the bug first.
2. Identify likely root cause and name the exact file/function involved.
3. Prefer the smallest safe patch.
4. Do not refactor unrelated files during a bugfix.
5. If no tests exist for the bug path, create a focused regression test.
6. Keep type hints complete and compatible with strict mypy.
7. Before finishing, run:
   - `ruff check .`
   - `black --check .`
   - `mypy .`
   - relevant tests if present
8. Summarize:
   - root cause
   - files changed
   - tests/checks run
   - remaining risk

## Constraints
- Do not add new dependencies without explicit approval.
- Do not modify public API behavior unless required by the bug.
- Do not make schema changes unless the bug is data-model related.
- Do not claim the fix is complete without verification.

## Examples
- "Fix why query-by-text returns 500 for vague prompts"
- "Fix duplicate insert bug in TimescaleDB"
- "Fix asyncpg connection pool error on startup"