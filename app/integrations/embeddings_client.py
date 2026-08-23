from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol

logger = logging.getLogger(__name__)


class EmbeddingsClient(Protocol):
    def embed(self, texts: List[str], model: str) -> List[List[float]]: ...


class OpenAIEmbeddingsClient:
    def __init__(
        self,
        api_key: str,
        dimensions: int = 1536,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.dimensions = dimensions
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        client = self._get_client()
        response = client.embeddings.create(
            model=model,
            input=texts,
            dimensions=self.dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]