from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.schemas.solicitudes import SolicitudAccesoIn, SolicitudAccesoOut
from app.services.solicitudes_acceso_service import SolicitudAccesoService

router = APIRouter()


@router.post(
    "/solicitudes-acceso",
    response_model=SolicitudAccesoOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"security": []},
)
def crear_solicitud_acceso(payload: SolicitudAccesoIn, request: Request) -> SolicitudAccesoOut:
    """Solicitud de acceso al servicio. Endpoint público, sin autenticación."""
    origen = (request.headers.get("origin") or "desconocido").strip()[:200] or "desconocido"
    solicitud = SolicitudAccesoService().crear(payload, origen=origen)
    if solicitud is None:
        # Honeypot: respuesta indistinguible de un alta exitosa, sin persistir nada.
        return SolicitudAccesoOut(id=0, estado="PENDIENTE", created_at=None)
    return SolicitudAccesoOut(
        id=solicitud["id"],
        estado=solicitud.get("estado") or "PENDIENTE",
        created_at=str(solicitud["created_at"]) if solicitud.get("created_at") else None,
    )
