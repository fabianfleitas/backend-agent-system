from __future__ import annotations

from typing import Dict

from pydantic import BaseModel


class MetricsOut(BaseModel):
    total_queries: int = 0
    total_conversations: int = 0
    total_documents: int = 0
    total_feedbacks: int = 0
    avg_response_time: float = 0.0
    avg_fidelity: float = 0.0
    avg_relevance: float = 0.0
    system_status: str = "healthy"


class ReadyOut(BaseModel):
    status: str
    services: Dict[str, bool]
