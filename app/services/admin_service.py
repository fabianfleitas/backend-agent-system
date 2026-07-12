from __future__ import annotations

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

        return MetricsOut(
            total_queries=len(messages),
            total_conversations=len(conversations),
            total_documents=len(documents),
            total_feedbacks=len(feedbacks),
            avg_response_time=round(_average(response_times), 2),
            avg_fidelity=round(_average(fidelities), 4),
            avg_relevance=round(_average(relevances), 4),
            system_status="healthy",
        )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


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
