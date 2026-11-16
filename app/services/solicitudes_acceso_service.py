from __future__ import annotations

import html
import logging
from typing import Any, Optional

from app.core.config import settings
from app.repositories.solicitudes_acceso_repository import SolicitudesAccesoRepository
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class SolicitudAccesoService:
    def __init__(
        self,
        repo: Optional[SolicitudesAccesoRepository] = None,
        notifier: Optional[NotificationService] = None,
    ) -> None:
        self.repo = repo or SolicitudesAccesoRepository()
        self.notifier = notifier or NotificationService()

    def es_posible_bot(self, empresa: Optional[str]) -> bool:
        """El campo trampa `empresa` debe llegar vacío; si trae algo, es un bot."""
        return bool((empresa or "").strip())

    def crear(self, payload: Any, origen: str = "desconocido") -> Optional[dict]:
        """Persiste la solicitud. Devuelve None si el honeypot detectó un bot."""
        if self.es_posible_bot(getattr(payload, "empresa", None)):
            logger.info("Solicitud de acceso descartada por honeypot")
            return None

        solicitud = self.repo.create(
            {
                "institucion_nombre": payload.institucion_nombre,
                "persona_contacto": payload.persona_contacto,
                "email": payload.email,
                "telefono": payload.telefono,
                "cantidad_usuarios_estimada": payload.cantidad_usuarios_estimada,
                "perfil_solicitado": payload.perfil_solicitado,
                "mensaje": payload.mensaje,
                "estado": "PENDIENTE",
                "origen": origen,
            }
        )
        self._avisar(solicitud)
        return solicitud

    def _avisar(self, solicitud: dict) -> None:
        """El aviso por correo falla suave: la solicitud ya quedó persistida."""
        destino = (settings.solicitudes_email or "").strip()
        if not destino:
            logger.info("SOLICITUDES_EMAIL no configurado; no se envía aviso de solicitud")
            return

        institucion = solicitud.get("institucion_nombre") or "(sin nombre)"
        asunto = f"Nueva solicitud de acceso: {institucion}"
        texto = self._cuerpo_texto(solicitud)
        try:
            self.notifier.send_automated(
                None,
                destinatario=destino,
                asunto=asunto,
                contenido="<pre>" + html.escape(texto) + "</pre>",
                contenido_texto=texto,
                tipo="SYSTEM",
                clave_idempotencia=f"solicitud-acceso:{solicitud.get('id')}",
            )
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo enviar el aviso de la solicitud de acceso")

    @staticmethod
    def _cuerpo_texto(solicitud: dict) -> str:
        campos = [
            ("Institución", solicitud.get("institucion_nombre")),
            ("Persona de contacto", solicitud.get("persona_contacto")),
            ("Correo", solicitud.get("email")),
            ("Teléfono", solicitud.get("telefono")),
            ("Usuarios estimados", solicitud.get("cantidad_usuarios_estimada")),
            ("Perfil solicitado", solicitud.get("perfil_solicitado")),
            ("Origen", solicitud.get("origen")),
            ("Mensaje", solicitud.get("mensaje")),
        ]
        lineas = [f"{etiqueta}: {valor}" for etiqueta, valor in campos if valor not in (None, "")]
        return "\n".join(lineas) or "Solicitud sin datos."
