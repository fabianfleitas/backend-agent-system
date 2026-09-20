from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.email_template_repository import EmailTemplateRepository


class EmailTemplateService:
    def __init__(self, repository: Optional[EmailTemplateRepository] = None) -> None:
        self.repository = repository or EmailTemplateRepository()

    def _scope(self, auth: AuthContext) -> Optional[int]:
        """institucion_id destino: None = global (platform), inst = institucional."""
        if auth.institucion_id is None and not auth.is_platform_admin:
            return None
        return None if auth.is_platform_admin else auth.institucion_id

    def list(self, auth: AuthContext) -> list[dict]:
        scope = self._scope(auth)
        if scope is None:
            if auth.is_platform_admin:
                return self.repository.list_global()
            return []
        return self.repository.list_by_institution(scope)

    def create(self, auth: AuthContext, payload) -> dict:
        scope = self._scope(auth)
        return self.repository.create(
            institucion_id=scope,
            codigo=payload.codigo,
            nombre=payload.nombre,
            asunto=payload.asunto,
            contenido_html=payload.contenido_html,
            contenido_texto=payload.contenido_texto,
            activo=payload.activo,
        )

    def _get_owned(self, auth: AuthContext, template_id: int) -> Optional[dict]:
        template = self.repository.get_by_id(template_id)
        if not template:
            return None
        if auth.is_platform_admin:
            return template
        if template.get("institucion_id") != auth.institucion_id:
            return None
        return template

    def update(self, auth: AuthContext, template_id: int, payload) -> Optional[dict]:
        if not self._get_owned(auth, template_id):
            return None
        return self.repository.update(
            template_id,
            codigo=payload.codigo,
            nombre=payload.nombre,
            asunto=payload.asunto,
            contenido_html=payload.contenido_html,
            contenido_texto=payload.contenido_texto,
            activo=payload.activo,
        )

    def deactivate(self, auth: AuthContext, template_id: int) -> Optional[dict]:
        if not self._get_owned(auth, template_id):
            return None
        return self.repository.deactivate(template_id)