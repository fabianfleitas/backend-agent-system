from __future__ import annotations

from typing import Optional, List, Any

from app.core.supabase import get_supabase_client


class ConfigParametersRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_param(self, clave: str, institucion_id: Optional[int] = None) -> Optional[dict]:
        # Resolucion: primero institucional, luego global (NULL primero en orden DESC)
        # Usamos .order con DESC por institucion_id (NULLs primero por defecto en DESC)
        query = (
            self.client.table("config_parametros")
            .select("*")
            .eq("clave", clave)
            .eq("activo", True)
            .order("institucion_id", desc=True)
            .limit(1)
        )
        # Si institucion_id es None, queremos el global primero -> DESC pone NULL primero
        # Si institucion_id es X, queremos X primero, luego NULL -> DESC funciona
        response = query.execute()
        data = response.data or []
        for row in data:
            if row.get("institucion_id") == institucion_id or (institucion_id is not None and row.get("institucion_id") is not None):
                if row.get("institucion_id") == institucion_id:
                    return row
        # Fallback manual si el orden DESC no funciono como esperado
        for row in data:
            if row.get("institucion_id") == institucion_id:
                return row
        for row in data:
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
        # Upsert por (institucion_id, clave)
        response = self.client.table("config_parametros").upsert(payload, on_conflict="(institucion_id, clave)").execute()
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
