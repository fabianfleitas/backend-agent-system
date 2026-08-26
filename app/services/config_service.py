from __future__ import annotations

import time
from typing import Optional, Any

from app.core.config import settings
from app.repositories.config_repository import ConfigParametersRepository


class ConfigService:
    """Resolucion de parametros con fallback .env → DB global → DB institucional."""

    def __init__(self, repo: Optional[ConfigParametersRepository] = None) -> None:
        self.repo = repo  # lazy init below
        self._cache: dict[tuple[Optional[int], str], tuple[Any, float]] = {}
        self._ttl_seconds = 60.0

    def _get_repo(self) -> ConfigParametersRepository:
        if self.repo is None:
            self.repo = ConfigParametersRepository()
        return self.repo

    def _cache_key(self, institucion_id: Optional[int], clave: str) -> tuple[Optional[int], str]:
        return (institucion_id, clave)

    def _get_cached(self, institucion_id: Optional[int], clave: str) -> Optional[Any]:
        key = self._cache_key(institucion_id, clave)
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if (time.time() - ts) > self._ttl_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _set_cached(self, institucion_id: Optional[int], clave: str, valor: Any) -> None:
        self._cache[self._cache_key(institucion_id, clave)] = (valor, time.time())

    def invalidate(self, clave: Optional[str] = None, institucion_id: Optional[int] = None) -> None:
        keys_to_remove = [
            k for k in self._cache
            if (clave is None or k[1] == clave) and (institucion_id is None or k[0] == institucion_id)
        ]
        for k in keys_to_remove:
            self._cache.pop(k, None)

    def _resolve(self, clave: str, institucion_id: Optional[int], default: str) -> str:
        cached = self._get_cached(institucion_id, clave)
        if cached is not None:
            return str(cached)
        try:
            row = self._get_repo().get_param(clave, institucion_id)
        except Exception:
            row = None
        if row is not None:
            value = row.get("valor")
            self._set_cached(institucion_id, clave, value)
            return str(value)
        # Fallback a .env (settings)
        env_value = getattr(settings, clave, None)
        if env_value is not None:
            # Cache fallback tambien para evitar repetida DB query
            self._set_cached(institucion_id, clave, env_value)
        return str(env_value) if env_value is not None else str(default)

    def get_str(self, clave: str, institucion_id: Optional[int] = None, default: str = "") -> str:
        return self._resolve(clave, institucion_id, default)

    def get_float(self, clave: str, institucion_id: Optional[int] = None, default: float = 0.0) -> float:
        try:
            raw = self._resolve(clave, institucion_id, str(default))
            return float(raw)
        except Exception:
            return float(default)

    def get_int(self, clave: str, institucion_id: Optional[int] = None, default: int = 0) -> int:
        try:
            raw = self._resolve(clave, institucion_id, str(default))
            return int(float(raw))
        except Exception:
            return int(default)

    def get_bool(self, clave: str, institucion_id: Optional[int] = None, default: bool = False) -> bool:
        try:
            raw = self._resolve(clave, institucion_id, str(default)).lower()
            return raw in ("true", "1", "yes", "t", "y")
        except Exception:
            return bool(default)

    def set(self, clave: str, valor: Any, tipo: str = "string", institucion_id: Optional[int] = None, descripcion: Optional[str] = None) -> dict:
        result = self._get_repo().set_param(clave, str(valor), tipo, institucion_id, descripcion)
        self.invalidate(clave, institucion_id)
        return result
