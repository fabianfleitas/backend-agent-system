from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core.security import AuthContext
from fastapi import HTTPException
from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.users_repository import UsersRepository


class ConversationsService:
    def __init__(
        self,
        conversations_repository: Optional[ConversationsRepository] = None,
        messages_repository: Optional[MessagesRepository] = None,
        users_repository: Optional[UsersRepository] = None,
    ) -> None:
        self.conversations_repository = conversations_repository or ConversationsRepository()
        self.messages_repository = messages_repository or MessagesRepository()
        self.users_repository = users_repository or UsersRepository()

    def create_conversation(self, auth: AuthContext) -> dict:
        self.users_repository.get_or_create_user(auth)
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        title = f"Conversación {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        return self.conversations_repository.create_conversation(
            auth.external_auth_id, title, auth.institucion_id
        )

    def get_owned_conversation(self, conversation_id: int, external_auth_id: str, institucion_id: int = None) -> Optional[dict]:
        conversation = self.conversations_repository.get_conversation(conversation_id, institucion_id=institucion_id)
        if not conversation or conversation.get("external_auth_id") != external_auth_id:
            return None
        return conversation

    def list_conversations(self, external_auth_id: str, include_hidden: bool, institucion_id: int) -> list[dict]:
        return self.conversations_repository.list_conversations(external_auth_id, include_hidden, institucion_id)

    def hide_conversation(self, external_auth_id: str, conversation_id: int, institucion_id: int) -> Optional[dict]:
        return self.conversations_repository.hide_conversation(external_auth_id, conversation_id, institucion_id)

    def get_messages(self, conversation_id: int) -> list[dict]:
        return self.messages_repository.get_conversation_messages(conversation_id)

    def count_messages(self, conversation_id: int) -> int:
        return self.messages_repository.count_conversation_messages(conversation_id)
