from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class RateLimitRule:
    prefix: str
    limit: int
    window_seconds: int


class TokenBucket:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self.tokens = float(limit)
        self.last_refill = time.time()

    def consume(self, tokens: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.limit, self.tokens + elapsed * (self.limit / self.window))
        self.last_refill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    def __init__(self) -> None:
        self.buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self.lock = threading.Lock()

    def check(self, key: str, rule: RateLimitRule) -> bool:
        bucket_key = (key, rule.prefix)
        with self.lock:
            bucket = self.buckets.get(bucket_key)
            if bucket is None or bucket.limit != rule.limit or bucket.window != rule.window_seconds:
                bucket = TokenBucket(rule.limit, rule.window_seconds)
                self.buckets[bucket_key] = bucket
            return bucket.consume()

    def prune_old(self, max_age_seconds: float = 300.0) -> None:
        now = time.time()
        with self.lock:
            stale = [k for k, b in self.buckets.items() if (now - b.last_refill) > max_age_seconds]
            for k in stale:
                del self.buckets[k]


class RateLimitMiddleware:
    def __init__(self, app, limiter: RateLimiter, rules: list[RateLimitRule], exempt: list[str] | None = None) -> None:
        self.app = app
        self.limiter = limiter
        self.rules = rules
        self.exempt = exempt or ["/health", "/ready", "/api/billing/stripe/webhook"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        for p in self.exempt:
            if path.startswith(p) or path == p:
                await self.app(scope, receive, send)
                return
        from app.core.config import settings
        if not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return
        # Resolver clave por IP
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            key = forwarded.decode("ascii").split(",")[0].strip()
        else:
            client = scope.get("client")
            key = client[0] if client else "unknown"
        # Buscar regla
        matched = None
        for r in self.rules:
            if path.startswith(r.prefix) or (r.prefix.endswith("/") and path.startswith(r.prefix)) or path == r.prefix.rstrip("/"):
                matched = r
                break
        if matched is None:
            # Regla por defecto
            from app.core.config import settings
            matched = RateLimitRule(
                prefix="/api",
                limit=getattr(settings, "rate_limit_default_limit", 300),
                window_seconds=getattr(settings, "rate_limit_default_window_seconds", 60),
            )
        allowed = self.limiter.check(key, matched)
        if not allowed:
            retry_after = int(matched.window_seconds)
            response = JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
