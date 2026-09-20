from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class SmtpConfigRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_config(self, institucion_id: Optional[int]) -> Optional[dict]:
        query = self.client.table("configuracion_smtp").select("*").limit(1)
        if institucion_id is None:
            query = query.is_("institucion_id", None)
        else:
            query = query.eq("institucion_id", institucion_id)
        resp = query.execute()
        return resp.data[0] if resp.data else None

    def upsert(
        self,
        institucion_id: Optional[int],
        *,
        servidor: str,
        puerto: int,
        cifrado: str,
        usuario: Optional[str],
        password_secret_ref: Optional[str],
        correo_remitente: str,
        nombre_remitente: Optional[str],
        timeout_segundos: int,
        activo: bool,
    ) -> dict:
        existing = self.get_config(institucion_id)
        payload = {
            "servidor": servidor,
            "puerto": puerto,
            "cifrado": cifrado,
            "usuario": usuario,
            "correo_remitente": correo_remitente,
            "nombre_remitente": nombre_remitente,
            "timeout_segundos": timeout_segundos,
            "activo": activo,
        }
        if password_secret_ref is not None:
            payload["password_secret_ref"] = password_secret_ref
        if existing:
            resp = self.client.table("configuracion_smtp").update(payload).eq("id", existing["id"]).execute()
        else:
            payload["institucion_id"] = institucion_id
            resp = self.client.table("configuracion_smtp").insert(payload).execute()
        return resp.data[0]