from __future__ import annotations

"""Tests del caché de configuración (RF-08: persistencia local y caché).

Cubren el comportamiento de `ConfigService`: resolución con precedencia
institucional → global → `.env`, caché en memoria con TTL, invalidación por
evento (`set`) y `invalidate` explícito. Usan un repositorio fake en memoria,
sin Supabase ni base de datos.

Ejecutar:
    python3 -m pytest tests/test_cache_settings.py
"""

from typing import Any, Optional

import pytest

from app.core.config import settings
from app.services.config_service import ConfigService


@pytest.fixture(autouse=True)
def _config_get_bool_returns_default():
    """Anula el fixture global de `tests/conftest.py` que fuerza `get_bool` al default.

    Este módulo valida la resolución real de `ConfigService.get_bool` (incluida la
    precedencia institucional y la conversión de valores), por lo que no debe
    aplicarse ese parche.
    """
    return None


class FakeConfigRepo:
    def __init__(self, rows: Optional[list[dict]] = None) -> None:
        self.rows: list[dict] = rows or []
        self.get_calls = 0
        self.set_calls = 0

    def get_param(self, clave: str, institucion_id: Optional[int] = None) -> Optional[dict]:
        self.get_calls += 1
        # Precedencia: institucional exacto y, si no, global (institucion_id None).
        for row in self.rows:
            if row["clave"] == clave and row.get("institucion_id") == institucion_id:
                return row
        for row in self.rows:
            if row["clave"] == clave and row.get("institucion_id") is None:
                return row
        return None

    def set_param(self, clave: str, valor: str, tipo: str = "string", institucion_id: Optional[int] = None, descripcion: Optional[str] = None) -> dict:
        self.set_calls += 1
        payload = {
            "clave": clave,
            "valor": str(valor),
            "tipo": tipo,
            "institucion_id": institucion_id,
            "descripcion": descripcion,
        }
        self.rows = [
            r for r in self.rows
            if not (r["clave"] == clave and r.get("institucion_id") == institucion_id)
        ]
        self.rows.append(payload)
        return payload


def _service(rows: Optional[list[dict]] = None) -> tuple[ConfigService, FakeConfigRepo]:
    repo = FakeConfigRepo(rows)
    return ConfigService(repo=repo), repo  # type: ignore[arg-type]


def test_get_str_lee_de_repo_y_luego_usa_cache() -> None:
    service, repo = _service([{"clave": "judge_enabled", "valor": "true", "institucion_id": None}])
    assert service.get_str("judge_enabled") == "true"
    assert service.get_str("judge_enabled") == "true"
    # La segunda lectura no debe volver a consultar el repositorio.
    assert repo.get_calls == 1


def test_get_bool_convierte_valores() -> None:
    service, _ = _service([{"clave": "handoff_enabled", "valor": "1", "institucion_id": None}])
    assert service.get_bool("handoff_enabled") is True

    service2, _ = _service([{"clave": "handoff_enabled", "valor": "no", "institucion_id": None}])
    assert service2.get_bool("handoff_enabled") is False


def test_precedencia_institucional_sobre_global() -> None:
    service, _ = _service(
        [
            {"clave": "judge_enabled", "valor": "false", "institucion_id": None},
            {"clave": "judge_enabled", "valor": "true", "institucion_id": 7},
        ]
    )
    assert service.get_bool("judge_enabled", institucion_id=7) is True
    # La caché es por (institucion_id, clave): el global no contamina al institucional.
    assert service.get_bool("judge_enabled", institucion_id=99) is False


def test_fallback_a_env_cuando_no_hay_fila() -> None:
    service, repo = _service([])
    # `pii_nlp_model` existe en settings (.env) y no en el repo.
    assert service.get_str("pii_nlp_model") == getattr(settings, "pii_nlp_model")
    assert service.get_str("pii_nlp_model") == getattr(settings, "pii_nlp_model")
    # El fallback también se cachea: una sola consulta al repo.
    assert repo.get_calls == 1


def test_ttl_expira_entrada_y_vuelve_a_consultar() -> None:
    service, repo = _service([{"clave": "judge_enabled", "valor": "true", "institucion_id": None}])
    assert service.get_str("judge_enabled") == "true"
    assert repo.get_calls == 1
    # Forzar expiración del TTL.
    service._ttl_seconds = -1.0
    assert service.get_str("judge_enabled") == "true"
    assert repo.get_calls == 2


def test_invalidate_limpia_la_entrada() -> None:
    service, repo = _service([{"clave": "judge_enabled", "valor": "true", "institucion_id": None}])
    assert service.get_str("judge_enabled") == "true"
    service.invalidate("judge_enabled")
    assert service.get_str("judge_enabled") == "true"
    assert repo.get_calls == 2


def test_set_persiste_e_invalida_cache() -> None:
    service, repo = _service([{"clave": "judge_enabled", "valor": "true", "institucion_id": None}])
    assert service.get_str("judge_enabled") == "true"
    service.set("judge_enabled", "false")
    # Tras `set`, la siguiente lectura refleja el nuevo valor persistido.
    assert service.get_str("judge_enabled") == "false"
    assert repo.set_calls == 1
