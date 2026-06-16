from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.core.supabase import get_supabase_client


class SystemRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def check_database(self) -> bool:
        try:
            self.client.table("app_users").select("id").limit(1).execute()
        except Exception:
            return False
        return True

    def check_storage(self) -> bool:
        try:
            self.client.storage.get_bucket(settings.supabase_storage_bucket_documents)
        except Exception:
            return False
        return True

    def check_vector_store(self) -> bool:
        try:
            self.client.table("document_embeddings").select("id").limit(1).execute()
        except Exception:
            return False
        return True
