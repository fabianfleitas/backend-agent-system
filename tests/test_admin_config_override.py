from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.admin.routes import update_config
from app.core.security import AuthContext
from app.repositories.audit_repository import AuditRepository
from app.repositories.config_repository import ConfigParametersRepository
from app.schemas.admin import ConfigParamIn

ADMIN = AuthContext(
    external_auth_id="adm1",
    institucion_id=1,
    tipo_miembro="ADMIN",
    is_platform_admin=False,
)


def _global_row(clave: str, editable: bool = True) -> dict:
    return {
        "id": 1,
        "institucion_id": None,
        "clave": clave,
        "valor": "openai/gpt-4o-mini",
        "tipo": "string",
        "descripcion": "global",
        "editable_desde_dashboard": editable,
        "activo": True,
        "created_at": None,
        "updated_at": None,
    }


def test_institutional_admin_can_create_override_over_global(monkeypatch) -> None:
    calls: list[dict] = []

    monkeypatch.setattr(
        ConfigParametersRepository,
        "get_param",
        lambda self, clave, institucion_id=None: _global_row(clave),
    )

    def fake_set_param(self, clave, valor, tipo="string", institucion_id=None, descripcion=None):
        row = {
            "id": 2,
            "institucion_id": institucion_id,
            "clave": clave,
            "valor": str(valor),
            "tipo": tipo,
            "descripcion": descripcion,
            "editable_desde_dashboard": True,
            "activo": True,
            "created_at": None,
            "updated_at": None,
        }
        calls.append(row)
        return row

    monkeypatch.setattr(ConfigParametersRepository, "set_param", fake_set_param)
    monkeypatch.setattr(AuditRepository, "create_audit_log", lambda self, **kwargs: None)

    result = update_config(
        "llm_model",
        ConfigParamIn(
            clave="llm_model",
            valor="institucion/modelo-x",
            tipo="string",
        ),
        auth=ADMIN,
    )

    assert calls == [
        {
            "id": 2,
            "institucion_id": 1,
            "clave": "llm_model",
            "valor": "institucion/modelo-x",
            "tipo": "string",
            "descripcion": None,
            "editable_desde_dashboard": True,
            "activo": True,
            "created_at": None,
            "updated_at": None,
        }
    ]
    assert result.institucion_id == 1
    assert result.valor == "institucion/modelo-x"


def test_institutional_admin_cannot_edit_non_editable_global(monkeypatch) -> None:
    monkeypatch.setattr(
        ConfigParametersRepository,
        "get_param",
        lambda self, clave, institucion_id=None: _global_row(clave, editable=False),
    )

    with pytest.raises(HTTPException) as exc:
        update_config(
            "llm_model",
            ConfigParamIn(clave="llm_model", valor="otro/modelo", tipo="string"),
            auth=ADMIN,
        )

    assert exc.value.status_code == 403
