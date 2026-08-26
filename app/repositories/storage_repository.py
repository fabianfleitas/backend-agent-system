from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.core.supabase import get_supabase_client


def _validate_bucket_path(path: str) -> str:
    if ".." in path or path.startswith("/") or path.startswith("\\"):
        raise ValueError("unsafe_bucket_path")
    return path


class StorageRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def upload_document(
        self,
        path: str,
        content: bytes,
        content_type: Optional[str],
        upsert: bool = False,
    ) -> str:
        return self.upload_file(
            bucket_name=settings.supabase_storage_bucket_documents,
            path=path,
            content=content,
            content_type=content_type,
            upsert=upsert,
        )

    def download_document(self, path: str) -> bytes:
        _validate_bucket_path(path)
        return (
            self.client.storage.from_(settings.supabase_storage_bucket_documents)
            .download(path)
        )

    def upload_audio(
        self,
        path: str,
        content: bytes,
        content_type: Optional[str],
        upsert: bool = False,
    ) -> str:
        return self.upload_file(
            bucket_name=settings.supabase_storage_bucket_audio,
            path=path,
            content=content,
            content_type=content_type,
            upsert=upsert,
        )

    def download_audio(self, path: str) -> bytes:
        _validate_bucket_path(path)
        return (
            self.client.storage.from_(settings.supabase_storage_bucket_audio)
            .download(path)
        )

    def upload_file(
        self,
        bucket_name: str,
        path: str,
        content: bytes,
        content_type: Optional[str],
        upsert: bool = False,
    ) -> str:
        bucket = self.client.storage.from_(bucket_name)
        path = _validate_bucket_path(path)
        bucket.upload(
            path,
            content,
            file_options={
                "content-type": content_type or "application/octet-stream",
                "upsert": str(upsert).lower(),
            },
        )
        return path
