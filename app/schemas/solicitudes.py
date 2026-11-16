from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Validación local de correo: evita depender de `email-validator`.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

PERFILES_SOLICITADOS = ("ADMINISTRACION", "SECRETARIA", "ESTUDIANTE", "A_CONFIRMAR")


class SolicitudAccesoIn(BaseModel):
    institucion_nombre: str = Field(min_length=2, max_length=160)
    persona_contacto: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=200)
    telefono: Optional[str] = Field(default=None, max_length=40)
    cantidad_usuarios_estimada: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    perfil_solicitado: Optional[str] = Field(default=None, max_length=30)
    mensaje: Optional[str] = Field(default=None, max_length=2000)
    consentimiento: bool
    # Campo trampa: debe llegar vacío. Los bots suelen completarlo.
    empresa: Optional[str] = Field(default="", max_length=200)

    @field_validator("institucion_nombre", "persona_contacto", "email")
    @classmethod
    def _requerido_sin_espacios(cls, valor: str) -> str:
        limpio = (valor or "").strip()
        if not limpio:
            raise ValueError("Campo obligatorio")
        return limpio

    @field_validator("telefono", "perfil_solicitado", "mensaje", "empresa")
    @classmethod
    def _opcional_sin_espacios(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None

    @field_validator("email")
    @classmethod
    def _email_valido(cls, valor: str) -> str:
        if not EMAIL_RE.match(valor):
            raise ValueError("Correo electrónico inválido")
        return valor

    @field_validator("perfil_solicitado")
    @classmethod
    def _perfil_valido(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        if valor not in PERFILES_SOLICITADOS:
            raise ValueError("Perfil solicitado inválido")
        return valor

    @field_validator("consentimiento")
    @classmethod
    def _consentimiento_obligatorio(cls, valor: bool) -> bool:
        if not valor:
            raise ValueError("Se requiere el consentimiento para el tratamiento de datos")
        return valor


class SolicitudAccesoOut(BaseModel):
    id: int
    estado: str
    created_at: Optional[str] = None
