from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.repositories.system_repository import SystemRepository
from app.schemas.system import ReadyOut


class SystemService:
    def __init__(self, repository: Optional[SystemRepository] = None) -> None:
        self.repository = repository or SystemRepository()

    def get_readiness(self) -> ReadyOut:
        database_ok = self.repository.check_database()
        storage_ok = self.repository.check_storage()
        vector_store_ok = self.repository.check_vector_store()
        openai_ok = bool(settings.openai_api_key)
        ready = database_ok and storage_ok and vector_store_ok

        return ReadyOut(
            status="ready" if ready else "not_ready",
            services={
                "database": database_ok,
                "storage": storage_ok,
                "vector_store": vector_store_ok,
                "openai": openai_ok,
            },
        )
