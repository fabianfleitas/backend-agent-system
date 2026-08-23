from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from typing import Optional

from app.repositories.metrics_repository import MetricsRepository
from app.repositories.users_repository import UsersRepository
from app.schemas.common import UserOut, UserRole
from app.schemas.system import MetricsOut


class AdminService:
    def __init__(
        self,
        users_repository: Optional[UsersRepository] = None,
        metrics_repository: Optional[MetricsRepository] = None,
    ) -> None:
        self.users_repository = users_repository or UsersRepository()
        self.metrics_repository = metrics_repository or MetricsRepository()

    def list_users(self) -> list[UserOut]:
        users = self.users_repository.list_users()
        return [
            UserOut(
                external_auth_id=user["external_auth_id"],
                email=user.get("email"),
                role=_role_out(user.get("role")),
                created_at=_parse_datetime(user["created_at"]),
                updated_at=_parse_datetime(user.get("updated_at") or user["created_at"]),
            )
            for user in users
        ]

    def get_metrics(self) -> MetricsOut:
        messages = self.metrics_repository.list_messages()
        conversations = self.metrics_repository.list_conversations()
        documents = self.metrics_repository.list_documents()
        feedbacks = self.metrics_repository.list_feedbacks()
        audit_logs = self.metrics_repository.list_audit_logs()
        message_documents = self.metrics_repository.list_message_documents()

        response_times = [
            float(message["tiempo_respuesta_ms"])
            for message in messages
            if message.get("tiempo_respuesta_ms") is not None and message.get("rol_mensaje") == "ASSISTANT"
        ]
        fidelities = [
            float(log["score_fidelidad"])
            for log in audit_logs
            if log.get("score_fidelidad") is not None
        ]
        relevances = [
            float(log["score_relevancia"])
            for log in audit_logs
            if log.get("score_relevancia") is not None
        ]

        ia = _aggregate_ia(audit_logs, message_documents)

        return MetricsOut(
            total_queries=len(messages),
            total_conversations=len(conversations),
            total_documents=len(documents),
            total_feedbacks=len(feedbacks),
            avg_response_time=round(_average(response_times), 2),
            avg_fidelity=round(_average(fidelities), 4),
            avg_relevance=round(_average(relevances), 4),
            system_status="healthy",
            total_llm_responses=ia["total_llm_responses"],
            total_guard=ia["total_guard"],
            total_llm_failed=ia["total_llm_failed"],
            guard_rate=ia["guard_rate"],
            llm_failed_rate=ia["llm_failed_rate"],
            total_tokens_input=ia["total_tokens_input"],
            total_tokens_output=ia["total_tokens_output"],
            tokens_by_model=ia["tokens_by_model"],
            avg_retrieval_similarity=ia["avg_retrieval_similarity"],
            total_voice_queries=ia["total_voice_queries"],
            total_text_queries=ia["total_text_queries"],
            avg_response_time_voice=ia["avg_response_time_voice"],
            avg_response_time_text=ia["avg_response_time_text"],
        )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _aggregate_ia(audit_logs: list[dict], message_documents: list[dict]) -> dict:
    outcomes = defaultdict(int)
    tokens_by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
    total_tokens_input = 0
    total_tokens_output = 0
    total_voice = 0
    total_text = 0
    voice_times: list[float] = []
    text_times: list[float] = []

    for log in audit_logs:
        observaciones = log.get("observaciones") or ""
        outcomes[_classify_outcome(observaciones)] += 1
        channel = _classify_channel(observaciones)
        if channel == "voice":
            total_voice += 1
        elif channel == "text":
            total_text += 1
        model = log.get("modelo_ia")
        if model:
            tokens_by_model[model]["input"] += int(log.get("tokens_input") or 0)
            tokens_by_model[model]["output"] += int(log.get("tokens_output") or 0)
        total_tokens_input += int(log.get("tokens_input") or 0)
        total_tokens_output += int(log.get("tokens_output") or 0)
        if log.get("tiempo_respuesta_ms") is not None:
            if channel == "voice":
                voice_times.append(float(log["tiempo_respuesta_ms"]))
            elif channel == "text":
                text_times.append(float(log["tiempo_respuesta_ms"]))

    denominator = outcomes["llm"] + outcomes["guard"] + outcomes["llm_failed"]
    guard_rate = (outcomes["guard"] / denominator) if denominator else 0.0
    llm_failed_rate = (outcomes["llm_failed"] / denominator) if denominator else 0.0

    similarities = [
        float(row["similarity_score"])
        for row in message_documents
        if row.get("similarity_score") is not None
    ]

    return {
        "total_llm_responses": outcomes["llm"],
        "total_guard": outcomes["guard"],
        "total_llm_failed": outcomes["llm_failed"],
        "guard_rate": round(guard_rate, 4),
        "llm_failed_rate": round(llm_failed_rate, 4),
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "tokens_by_model": dict(tokens_by_model),
        "avg_retrieval_similarity": round(_average(similarities), 4),
        "total_voice_queries": total_voice,
        "total_text_queries": total_text,
        "avg_response_time_voice": round(_average(voice_times), 2),
        "avg_response_time_text": round(_average(text_times), 2),
    }


def _classify_outcome(observaciones: str) -> str:
    if observaciones.startswith("LLM:"):
        return "llm"
    if observaciones.startswith("GUARD:"):
        return "guard"
    if observaciones.startswith("LLM_FAILED:"):
        return "llm_failed"
    return "mock"


def _classify_channel(observaciones: str) -> Optional[str]:
    if "[voice]" in observaciones:
        return "voice"
    if "[text]" in observaciones:
        return "text"
    return None


def _role_out(role: Optional[str]) -> UserRole:
    mapping = {"ADMIN": UserRole.ADMIN, "STAFF": UserRole.STAFF, "STUDENT": UserRole.STUDENT}
    return mapping.get(role or "", UserRole.STUDENT)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    match = re.search(r"\.(\d+)([+-]\d{2}:\d{2})$", normalized)
    if match:
        fraction, offset = match.groups()
        normalized = normalized.replace(f".{fraction}{offset}", f".{fraction.ljust(6, '0')[:6]}{offset}")
    return datetime.fromisoformat(normalized)
