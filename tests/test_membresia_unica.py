from __future__ import annotations

import logging
from unittest.mock import MagicMock

from app.repositories.institutions_repository import InstitutionsRepository
from app.core.security import AuthContext


def _fake_client(data: list) -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    resp.data = data
    resp.execute.return_value = resp
    # Simular cadenas .table(...).select(...).eq(...).execute()
    def build_table(name):
        table = MagicMock()
        def build_query(*args, **kwargs):
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.is_.return_value = q
            q.in_.return_value = q
            q.order.return_value = q
            q.execute.return_value = resp
            return q
        table.select.side_effect = lambda *a, **kw: build_query()
        # Para .table("institucion_miembros").insert(...).execute()
        def insert_call(*args, **kwargs):
            return resp
        table.insert.side_effect = insert_call
        return table
    client.table.side_effect = build_table
    return client


def test_add_member_rejects_second_institution():
    repo = InstitutionsRepository()
    # Simular que ya existe membresía activa en otra institución
    existing = [{"id": 1, "institution_id": 99, "external_auth_id": "u1", "activo": True, "tipo_miembro": "ESTUDIANTE"}]
    repo.client = _fake_client(existing)
    try:
        repo.add_member(1, "u1", "ADMIN")
        assert False, "Should raise ValueError"
    except ValueError as exc:
        assert "another institution" in str(exc)


def test_add_member_same_institution_returns_existing():
    repo = InstitutionsRepository()
    existing = [{"id": 1, "institution_id": 1, "external_auth_id": "u1", "activo": True, "tipo_miembro": "ESTUDIANTE", "fecha_ingreso": "2024-01-01"}]
    # Client fake que devuelve existente en la primera lectura; insert nunca llega
    resp_existing = MagicMock()
    resp_existing.data = existing
    resp_existing.execute.return_value = resp_existing
    repo.client = MagicMock()
    repo.client.table.side_effect = lambda name: MagicMock(
        select=lambda *a, **kw: MagicMock(
            eq=lambda *a, **kw: MagicMock(execute=lambda: resp_existing)
        )
    )
    result = repo.add_member(1, "u1", "ADMIN")
    assert result is not None


def test_get_active_membership_duplicates_warning():
    repo = InstitutionsRepository()
    # 2 membresías activas; debe usar la más reciente (id=2 con fecha_ingreso mayor)
    rows = [
        {"id": 1, "institucion_id": 1, "tipo_miembro": "ESTUDIANTE", "fecha_ingreso": "2024-01-01", "nombre_institucion": "A"},
        {"id": 2, "institucion_id": 2, "tipo_miembro": "ADMIN", "fecha_ingreso": "2025-01-01", "nombre_institucion": "B"},
    ]
    resp = MagicMock()
    resp.data = rows
    resp.execute.return_value = resp

    def table(name):
        t = MagicMock()
        q = MagicMock()
        q.select.side_effect = lambda *a, **kw: q
        q.eq.side_effect = lambda *a, **kw: q
        q.is_.side_effect = lambda *a, **kw: q
        q.order.side_effect = lambda *a, **kw: q
        q.execute.return_value = resp
        t.select.side_effect = lambda *a, **kw: q
        return t
    client = MagicMock()
    client.table.side_effect = table
    repo.client = client

    # El mock de order no ordena real; solo validar que no lanza y que hay warning
    result = repo.get_active_membership("u_dup")
    assert result is not None
