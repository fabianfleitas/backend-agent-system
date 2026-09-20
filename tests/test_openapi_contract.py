from __future__ import annotations

from app.main import create_app


def test_openapi_has_security_scheme() -> None:
    app = create_app()
    schema = app.openapi()
    comps = schema.get("components", {})
    assert "securitySchemes" in comps
    assert "bearerAuth" in comps["securitySchemes"]
    assert comps["securitySchemes"]["bearerAuth"]["type"] == "http"


def test_openapi_has_global_security() -> None:
    app = create_app()
    schema = app.openapi()
    assert "security" in schema
    assert any("bearerAuth" in s for s in schema["security"])


def test_openapi_description_includes_errors() -> None:
    app = create_app()
    schema = app.openapi()
    desc = schema.get("info", {}).get("description", "")
    assert "401" in desc
    assert "403" in desc
    assert "404" in desc
    assert "409" in desc
    assert "422" in desc
    assert "500" in desc


def test_openapi_is_deterministic() -> None:
    app = create_app()
    s1 = app.openapi()
    s2 = create_app().openapi()
    assert s1 == s2
