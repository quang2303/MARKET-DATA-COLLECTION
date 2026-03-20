"""
tests/test_health.py

Test the /health endpoint.
"""

import pytest


async def test_health_returns_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    resp = await app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
