---
name: timescaledb-dedupe-migration
description: Use this skill when changing TimescaleDB schema, insert logic, deduplication, idempotent ingestion, indexes, retention/compression policy, or asyncpg bulk insert behavior in the market-data project.
---

# TimescaleDB Dedupe Migration Skill

## Goal
Make database changes safely for OHLCV market data, with emphasis on deduplication, idempotent ingestion, and query safety.

## Repository Context
- Database code lives in `db/`
- Storage is TimescaleDB/PostgreSQL
- OHLCV is the canonical market data model
- The repo stores candlestick data and queries it through FastAPI

## Instructions
1. Inspect current DB model and insert path before changing anything.
2. Check whether the proposed change impacts:
   - uniqueness of candles
   - bulk insert performance
   - existing query compatibility
   - retention/compression behavior
3. For OHLCV data, always think about uniqueness on:
   - `symbol`
   - `timeframe`
   - `timestamp`
4. Prefer idempotent writes.
5. If changing schema:
   - write migration SQL clearly
   - explain rollback or fallback path
6. If changing insert logic:
   - verify compatibility with asyncpg bulk insert
   - preserve model contract from `core/models.py`
7. Verify by showing:
   - affected SQL
   - affected Python DB path
   - risk of duplicates
   - expected performance impact

## Constraints
- Do not drop tables or destructive policies unless explicitly asked.
- Do not silently change time semantics or column meanings.
- Do not widen scope into unrelated API refactors.

## Output Format
Always end with:
- Problem
- Proposed DB change
- Python files to change
- Verification steps
- Risk level