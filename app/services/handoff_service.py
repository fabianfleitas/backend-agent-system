from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.repositories.notifications_repository import NotificationsRepository
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

WORKFLOW_PENDING = "PENDING"
WORKFLOW_RESOLVED = "RESOLVED"
WORKFLOW_CANCELLED = "CANCELLED"

RECIPIENT_LABEL = "SECRETARIA"


class HandoffService:
    """Derivación a operador humano (RF-06) reutilizando la tabla `notificaciones`.

    Se modela como notificación `tipo='SYSTEM'`, `canal='IN_APP'`, con el flujo
    de trabajo (PENDING/RESOLVED) en `datos.workflow_estado`. No requiere cambios
    de esquema.
    """

    def __init__(
        self,
        notifications_repo: Optional[NotificationsRepository] = None,
        config_service: Optional[ConfigService] = None,
    ) -> None:
        # Repo lazy: no construye el cliente Supabase hasta que se persiste.
        self.notifications_repo = notifications_repo
        self.config_service = config_service or ConfigService()

    def _repo(self) -> NotificationsRepository:
        if self.notifications_repo is None:
            self.notifications_repo = NotificationsRepository()
        return self.notifications_repo

    def enabled(self, institucion_id: Optional[int]) -> bool:
        return self.config_service.get_bool(
            "handoff_enabled", institucion_id, settings.handoff_enabled
        )

    def should_escalate(
        self,
        message: str,
        institucion_id: Optional[int],
        guard_triggered: bool = False,
        llm_failed: bool = False,
    ) -> Optional[str]:
        """Devuelve el motivo de escalamiento o None si no corresponde."""
        if not self.enabled(institucion_id):
            return None
        if guard_triggered and self.config_service.get_bool(
            "handoff_trigger_on_guard", institucion_id, settings.handoff_trigger_on_guard
        ):
            return "DOMAIN_OUT_OF_SCOPE"
        if llm_failed and self.config_service.get_bool(
            "handoff_trigger_on_llm_failure",
            institucion_id,
            settings.handoff_trigger_on_llm_failure,
        ):
            return "LLM_FAILURE"
        if self.config_service.get_bool(
            "handoff_frustration_enabled",
            institucion_id,
            settings.handoff_frustration_enabled,
        ) and self._detect_frustration(message):
            return "FRUSTRATION"
        return None

    def create_escalation(
        self,
        *,
        institucion_id: Optional[int],
        conversacion_id: int,
        mensaje_id: int,
        audit_id: str,
        external_auth_id: str,
        motivo: str,
        resumen: str,
    ) -> Optional[dict]:
        clave = f"handoff:{audit_id}"
        existing = self._repo().get_by_idempotency(clave)
        if existing:
            return existing
        datos = {
            "escalamiento": True,
            "motivo": motivo,
            "resumen": resumen,
            "conversacion_id": conversacion_id,
            "mensaje_id": mensaje_id,
            "audit_id": audit_id,
            "external_auth_id": external_auth_id,
            "workflow_estado": WORKFLOW_PENDING,
            "resolved_by": None,
            "resolved_at": None,
        }
        payload = {
            "institucion_id": institucion_id,
            "tipo": "SYSTEM",
            "canal": "IN_APP",
            "destinatario": RECIPIENT_LABEL,
            "asunto": f"Escalamiento: {motivo}",
            "contenido": (resumen or "")[:2000],
            "estado": "PENDING",
            "clave_idempotencia": clave,
            "datos": datos,
        }
        try:
            return self._repo().create(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Escalation persist failed audit_id=%s motivo=%s error=%s",
                audit_id,
                motivo,
                exc,
            )
            return None

    def resolve_escalation(
        self,
        notification_id: int,
        resolved_by: str,
    ) -> Optional[dict]:
        repo = self._repo()
        current = repo.get_by_id(notification_id)
        if not current:
            return None
        datos = dict(current.get("datos") or {})
        datos["workflow_estado"] = WORKFLOW_RESOLVED
        datos["resolved_by"] = resolved_by
        datos["resolved_at"] = datetime.now(timezone.utc).isoformat()
        return repo.update_datos(notification_id, datos)

    def list_escalamientos(
        self,
        institucion_id: int,
        workflow_estado: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        return self._repo().list_escalamientos(
            institucion_id=institucion_id,
            workflow_estado=workflow_estado,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _detect_frustration(text: str) -> bool:
        lowered = (text or "").lower()
        keywords = [k.strip() for k in settings.handoff_frustration_keywords.split(",") if k.strip()]
        return any(kw in lowered for kw in keywords)