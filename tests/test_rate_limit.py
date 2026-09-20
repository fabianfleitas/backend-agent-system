from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import RateLimiter, RateLimitMiddleware, RateLimitRule


def _make_app(rules, enabled=True):
    settings.rate_limit_enabled = enabled
    limiter = RateLimiter()
    app = FastAPI()
    @app.get("/test")
    def endpoint():
        return {"ok": True}
    app.add_middleware(RateLimitMiddleware, limiter=limiter, rules=rules, exempt=[])
    return app


def test_rate_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    rules = [RateLimitRule(prefix="/test", limit=2, window_seconds=60)]
    app = _make_app(rules)
    client = TestClient(app)
    r1 = client.get("/test")
    assert r1.status_code == 200
    r2 = client.get("/test")
    assert r2.status_code == 200
    r3 = client.get("/test")
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers


def test_rate_limit_disabled_no_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    rules = [RateLimitRule(prefix="/test", limit=1, window_seconds=60)]
    app = _make_app(rules, enabled=False)
    client = TestClient(app)
    r = client.get("/test")
    assert r.status_code == 200
