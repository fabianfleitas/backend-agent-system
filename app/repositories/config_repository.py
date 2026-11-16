from __future__ import annotations

from typing import Optional, List, Any

from app.core.supabase import get_supabase_client


class ConfigParametersRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_param(self, clave: str, institucion_id: Optional[int] = None) -> Optional[dict]:
        # Precedencia: institucional exacto y, si no, global (institucion_id NULL).
        # No usar LIMIT 1: el orden de PostgREST puede devolver primero el global
        # y ocultar el override institucional.
        query = (
            self.client.table("config_parametros")
            .select("*")
            .eq("clave", clave)
            .eq("activo", True)
        )
        response = query.execute()
        rows = response.data or []
        if institucion_id is not None:
            for row in rows:
                if row.get("institucion_id") == institucion_id:
                    return row
        for row in rows:
            if row.get("institucion_id") is None:
                return row
        return None

    def set_param(
        self,
        clave: str,
        valor: str,
        tipo: str = "string",
        institucion_id: Optional[int] = None,
        descripcion: Optional[str] = None,
    ) -> Optional[dict]:
        payload = {
            "clave": clave,
            "valor": str(valor),
            "tipo": tipo,
            "institucion_id": institucion_id,
            "descripcion": descripcion,
            "editable_desde_dashboard": True,
            "activo": True,
        }
        # PostgREST espera `on_conflict=col1,col2` (sin paréntesis).
        # Para filas globales (institucion_id NULL) el UNIQUE no aplica
        # (NULLs distintos), por lo que se actualiza por id si ya existe.
        if institucion_id is None:
            existing = self.get_param(clave, None)
            if existing is not None and existing.get("institucion_id") is None:
                response = (
                    self.client.table("config_parametros")
                    .update(payload)
                    .eq("id", existing["id"])
                    .execute()
                )
            else:
                response = self.client.table("config_parametros").insert(payload).execute()
            return response.data[0] if response.data else None

        response = self.client.table("config_parametros").upsert(
            payload, on_conflict="institucion_id,clave"
        ).execute()
        return response.data[0] if response.data else None

    def list_params(self, institucion_id: Optional[int] = None) -> List[dict]:
        query = self.client.table("config_parametros").select("*").eq("activo", True)
        if institucion_id is not None:
            query = query.or_(f"institucion_id.eq.{institucion_id},institucion_id.is.null")
        else:
            # Global only? Actually for dashboard admin we want global + all institutional
            pass  # no filter = all
        response = query.execute()
        return list(response.data or [])

    def list_by_institution(self, institucion_id: int) -> List[dict]:
        response = (
            self.client.table("config_parametros")
            .select("*")
            .eq("activo", True)
            .or_(f"institucion_id.eq.{institucion_id},institucion_id.is.null")
            .execute()
        )
        return list(response.data or [])
