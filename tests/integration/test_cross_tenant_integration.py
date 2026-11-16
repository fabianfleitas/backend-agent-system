from __future__ import annotations

"""Prueba de integración real contra Supabase (marcada `integration`).

Verifica la política de la migración 004 (`uq_institucion_miembros_unica_activa`):
un usuario no puede tener dos membresías institucionales ACTIVAS simultáneas.

Requiere `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` configurados y el esquema
aplicado. Crea y elimina sus propios datos con identificadores únicos, por lo que
es seguro ejecutarla contra una base de desarrollo. Ejecutar:

    python3 -m pytest -m integration -v
"""

import uuid

import pytest

pytest.importorskip("supabase")

from app.core.config import settings  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture()
def supabase_client():
    if not settings.supabase_configured:
        pytest.skip("Requiere SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY configurados")
    from app.core.supabase import get_supabase_client

    return get_supabase_client()


def test_integration_membresia_unica_activa(supabase_client) -> None:
    """La segunda membresía activa del mismo usuario debe ser rechazada."""
    client = supabase_client
    suffix = uuid.uuid4().hex[:12]
    external_auth_id = f"qa-int-{suffix}"
    email = f"qa-int-{suffix}@ejemplo-test.edu"
    codigos = [f"QA-INT-{suffix}-A", f"QA-INT-{suffix}-B"]
    institucion_ids: list[int] = []

    try:
        # 1) Usuario de prueba (FK de institucion_miembros.external_auth_id).
        client.table("app_users").insert(
            {
                "external_auth_id": external_auth_id,
                "email": email,
                "full_name": "QA Integración",
                "is_active": True,
            }
        ).execute()

        # 2) Dos instituciones distintas.
        for nombre, codigo in zip(("QA Int A", "QA Int B"), codigos):
            resp = (
                client.table("instituciones")
                .insert({"nombre": nombre, "codigo": codigo, "activo": True})
                .execute()
            )
            institucion_ids.append(resp.data[0]["id"])

        # 3) Primera membresía activa: debe aceptarse.
        client.table("institucion_miembros").insert(
            {
                "institucion_id": institucion_ids[0],
                "external_auth_id": external_auth_id,
                "tipo_miembro": "ESTUDIANTE",
                "activo": True,
            }
        ).execute()

        # 4) Segunda membresía activa (otra institución): debe fallar por el índice 004.
        with pytest.raises(Exception) as excinfo:
            client.table("institucion_miembros").insert(
                {
                    "institucion_id": institucion_ids[1],
                    "external_auth_id": external_auth_id,
                    "tipo_miembro": "ESTUDIANTE",
                    "activo": True,
                }
            ).execute()

        mensaje = str(excinfo.value).lower()
        assert (
            "uq_institucion_miembros_unica_activa" in mensaje
            or "duplicate" in mensaje
            or "unique" in mensaje
        ), f"Se esperaba violación de unicidad, se obtuvo: {excinfo.value}"

        # 5) Una membresía inactiva del mismo usuario sí debe permitirse.
        client.table("institucion_miembros").insert(
            {
                "institucion_id": institucion_ids[1],
                "external_auth_id": external_auth_id,
                "tipo_miembro": "ESTUDIANTE",
                "activo": False,
            }
        ).execute()
    finally:
        # Limpieza tolerante a fallos intermedios.
        client.table("institucion_miembros").delete().eq(
            "external_auth_id", external_auth_id
        ).execute()
        for institucion_id in institucion_ids:
            client.table("instituciones").delete().eq("id", institucion_id).execute()
        client.table("app_users").delete().eq(
            "external_auth_id", external_auth_id
        ).execute()
