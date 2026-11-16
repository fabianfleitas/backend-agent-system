from __future__ import annotations

"""S9 — Auditoría de acciones de gestión (CU-50).

Verifica que `AuditRepository.log_action` persiste acciones administrativas con
`conversacion_id`/`mensaje_id` NULL, y que el mapeo `_audit_out` tolera esa forma.
"""

from app.repositories.audit_repository import AuditRepository


class _FakeTable:
    def __init__(self) -> None:
        self.insert_payload = None

    def insert(self, payload: dict):
        self.insert_payload = payload
        return self

    def execute(self):
        return type("R", (), {"data": [dict(self.insert_payload, id="audit-x")]})


class _FakeClient:
    def __init__(self) -> None:
        self.table_name = None
        self.table_inst = _FakeTable()

    def table(self, name: str):
        self.table_name = name
        return self.table_inst


def test_log_action_inserta_accion_sin_mensaje() -> None:
    client = _FakeClient()
    repo = AuditRepository(client=client)  # type: ignore[arg-type]
    row = repo.log_action(
        "DOC_UPLOAD",
        external_auth_id="adm-1",
        institucion_id=3,
        detalle="documento_id=10 version_id=11",
    )
    assert row is not None
    payload = client.table_inst.insert_payload
    assert payload["respuesta_texto"] == "DOC_UPLOAD"
    assert payload["conversacion_id"] is None
    assert payload["mensaje_id"] is None
    assert payload["external_auth_id"] == "adm-1"
    assert payload["institucion_id"] == 3
    assert payload["observaciones"] == "documento_id=10 version_id=11"


def test_log_action_permite_detalle_nulo() -> None:
    client = _FakeClient()
    repo = AuditRepository(client=client)  # type: ignore[arg-type]
    row = repo.log_action("FEEDBACK_HIDE", external_auth_id="adm-1", institucion_id=3)
    assert row is not None
    assert client.table_inst.insert_payload["respuesta_texto"] == "FEEDBACK_HIDE"


def test_billing_log_action_uses_audit_repository(monkeypatch) -> None:
    """S9: el helper de billing registra BILLING_* vía AuditRepository.log_action."""
    import app.services.billing_service as bs
    from app.core.security import AuthContext

    class _FakeAudit:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def log_action(self, action, *, external_auth_id, institucion_id=None, detalle=None):
            self.calls.append(
                {
                    "action": action,
                    "external_auth_id": external_auth_id,
                    "institucion_id": institucion_id,
                    "detalle": detalle,
                }
            )
            return {"id": "audit-x"}

    fake = _FakeAudit()
    monkeypatch.setattr("app.repositories.audit_repository.AuditRepository", lambda: fake)

    auth = AuthContext(external_auth_id="adm-1", institucion_id=2, tipo_miembro="ADMIN")
    bs._log_billing_action("BILLING_CANCEL", auth, "subscription_id=1")
    bs._log_billing_action("BILLING_CHECKOUT", auth, "plan_id=3")

    assert [c["action"] for c in fake.calls] == ["BILLING_CANCEL", "BILLING_CHECKOUT"]
    assert fake.calls[0]["external_auth_id"] == "adm-1"
    assert fake.calls[0]["institucion_id"] == 2
    assert fake.calls[0]["detalle"] == "subscription_id=1"


def test_audit_out_tolera_mensaje_id_nulo() -> None:
    from app.api.admin.routes import _audit_out

    out = _audit_out(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "mensaje_id": None,
            "score_fidelidad": None,
            "score_relevancia": None,
            "score_contexto": None,
            "observaciones": "CATEGORY_CREATE categoria_id=5",
            "fecha_evaluacion": "2026-09-22T00:00:00Z",
        }
    )
    assert out.mensaje_id is None
    assert out.observaciones.startswith("CATEGORY_CREATE")