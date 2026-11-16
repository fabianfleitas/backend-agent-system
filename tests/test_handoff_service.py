from __future__ import annotations

from typing import Optional

from app.services.handoff_service import (
    HandoffService,
    WORKFLOW_PENDING,
    WORKFLOW_RESOLVED,
)


class FakeNotificationsRepo:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.next_id = 1

    def get_by_idempotency(self, clave_idempotencia: str) -> Optional[dict]:
        return next((r for r in self.rows if r.get("clave_idempotencia") == clave_idempotencia), None)

    def get_by_id(self, notification_id: int) -> Optional[dict]:
        return next((r for r in self.rows if r.get("id") == notification_id), None)

    def create(self, payload: dict) -> dict:
        record = dict(payload)
        record["id"] = self.next_id
        self.next_id += 1
        self.rows.append(record)
        return record

    def list_escalamientos(self, institucion_id: int, workflow_estado=None, limit=50, offset=0) -> list[dict]:
        rows = [
            r for r in self.rows
            if r.get("institucion_id") == institucion_id
            and r.get("tipo") == "SYSTEM"
            and isinstance(r.get("datos"), dict)
            and r["datos"].get("escalamiento") is True
        ]
        if workflow_estado is not None:
            rows = [r for r in rows if r["datos"].get("workflow_estado") == workflow_estado]
        return list(rows[offset : offset + limit])

    def update_datos(self, notification_id: int, datos: dict) -> Optional[dict]:
        for r in self.rows:
            if r.get("id") == notification_id:
                r["datos"] = datos
                return r
        return None


class FakeConfig:
    def __init__(self, values: Optional[dict] = None) -> None:
        self.values = values or {}

    def get_bool(self, clave: str, institucion_id: Optional[int] = None, default: bool = False) -> bool:
        return self.values.get(clave, default)


def _service(enabled: bool = True, values: Optional[dict] = None) -> HandoffService:
    cfg = FakeConfig(values or {"handoff_enabled": enabled})
    return HandoffService(
        notifications_repo=FakeNotificationsRepo(),  # type: ignore[arg-type]
        config_service=cfg,  # type: ignore[arg-type]
    )


def test_disabled_no_escala() -> None:
    svc = _service(enabled=False)
    assert svc.should_escalate("consulta", institucion_id=1, guard_triggered=True) is None


def test_guard_trigger_escala() -> None:
    svc = _service()
    motivo = svc.should_escalate("consulta fuera de alcance", institucion_id=1, guard_triggered=True)
    assert motivo == "DOMAIN_OUT_OF_SCOPE"


def test_llm_failure_escala() -> None:
    svc = _service()
    motivo = svc.should_escalate("consulta", institucion_id=1, llm_failed=True)
    assert motivo == "LLM_FAILURE"


def test_frustration_detects_keywords() -> None:
    svc = _service(values={"handoff_enabled": True, "handoff_frustration_enabled": True})
    assert svc._detect_frustration("esto no me sirve") is True
    assert svc._detect_frustration("¿horarios de matrícula?") is False


def test_create_escalation_idempotente() -> None:
    svc = _service()
    first = svc.create_escalation(
        institucion_id=1,
        conversacion_id=5,
        mensaje_id=9,
        audit_id="audit-1",
        external_auth_id="student-1",
        motivo="DOMAIN_OUT_OF_SCOPE",
        resumen="consulta",
    )
    second = svc.create_escalation(
        institucion_id=1,
        conversacion_id=5,
        mensaje_id=9,
        audit_id="audit-1",
        external_auth_id="student-1",
        motivo="DOMAIN_OUT_OF_SCOPE",
        resumen="consulta",
    )
    assert first is not None
    assert second is not None
    assert first["id"] == second["id"]
    assert first["datos"]["workflow_estado"] == WORKFLOW_PENDING
    assert first["clave_idempotencia"] == "handoff:audit-1"


def test_resolve_escalation() -> None:
    svc = _service()
    created = svc.create_escalation(
        institucion_id=1,
        conversacion_id=5,
        mensaje_id=9,
        audit_id="audit-1",
        external_auth_id="student-1",
        motivo="LLM_FAILURE",
        resumen="fallo",
    )
    updated = svc.resolve_escalation(created["id"], resolved_by="admin-1")
    assert updated is not None
    assert updated["datos"]["workflow_estado"] == WORKFLOW_RESOLVED
    assert updated["datos"]["resolved_by"] == "admin-1"
    assert updated["datos"]["resolved_at"] is not None