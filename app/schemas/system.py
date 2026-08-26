from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class MetricSeriesPoint(BaseModel):
    fecha: str
    conversaciones: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    llm: int = 0
    guard: int = 0
    llm_failed: int = 0

class MetricsOut(BaseModel):
    total_queries: int = 0
    total_conversations: int = 0
    total_documents: int = 0
    total_feedbacks: int = 0
    avg_response_time: float = 0.0
    avg_fidelity: float = 0.0
    avg_relevance: float = 0.0
    system_status: str = "healthy"

    total_llm_responses: int = 0
    total_guard: int = 0
    total_llm_failed: int = 0
    guard_rate: float = 0.0
    llm_failed_rate: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    tokens_by_model: Dict[str, Dict[str, int]] = {}
    avg_retrieval_similarity: float = 0.0
    total_voice_queries: int = 0
    total_text_queries: int = 0
    avg_response_time_voice: float = 0.0
    avg_response_time_text: float = 0.0
    series: List[MetricSeriesPoint] = []
    # Echo de filtros aplicados
    desde: Optional[str] = None
    hasta: Optional[str] = None
    categoria_id: Optional[int] = None
    modelo: Optional[str] = None
    documento_id: Optional[int] = None
    granularidad: Optional[str] = "day"


class ReadyOut(BaseModel):
    status: str
    services: Dict[str, bool]
