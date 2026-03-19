---
name: query-by-text-guardrails
description: Use this skill when working on the natural-language market query flow powered by Gemini, especially prompt parsing, structured output, parameter validation, FastAPI endpoint behavior, and user-facing error handling.
---

# Query By Text Guardrails Skill

## Goal
Keep the natural-language query flow reliable, validated, and user-safe.

## Repository Context
- Endpoint: `POST /api/v1/query-by-text`
- The system uses Gemini structured output to turn text into DB query parameters
- Downstream code must query the database safely and return predictable errors

## Instructions
1. Inspect the full path:
   user text -> LLM parse -> schema validation -> DB query -> API response
2. Validate extracted parameters:
   - symbol present and normalized
   - timeframe allowed
   - start/end time valid
   - end > start
   - range size not excessive
3. Convert vague or missing info into clear user-facing errors.
4. Separate error classes where possible:
   - validation error
   - LLM parse failure
   - DB error
   - no data found
5. Preserve stable API response shape.
6. Add focused tests for edge prompts:
   - ambiguous timeframe
   - missing symbol
   - unsupported asset
   - invalid date range
7. If prompt instructions are changed, explain why and show before/after behavior.

## Constraints
- Do not silently guess dangerous query ranges.
- Do not return raw internal exceptions to the client.
- Do not break the explicit `GET /api/v1/market-data` contract.

## Examples
- "Fix query-by-text when user says 'give me BTC last week'"
- "Improve errors when Gemini returns incomplete structured output"
- "Add validation for huge date windows"