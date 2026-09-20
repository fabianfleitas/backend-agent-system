from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from app.core.security import AuthContext
from fastapi import HTTPException
from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.message_documents_repository import MessageDocumentsRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.users_repository import UsersRepository


class ConversationsService:
    def __init__(
        self,
        conversations_repository: Optional[ConversationsRepository] = None,
        messages_repository: Optional[MessagesRepository] = None,
        users_repository: Optional[UsersRepository] = None,
        message_documents_repository: Optional[MessageDocumentsRepository] = None,
        feedback_repository: Optional[FeedbackRepository] = None,
    ) -> None:
        self.conversations_repository = conversations_repository or ConversationsRepository()
        self.messages_repository = messages_repository or MessagesRepository()
        self.users_repository = users_repository or UsersRepository()
        self.message_documents_repository = message_documents_repository or MessageDocumentsRepository()
        self.feedback_repository = feedback_repository or FeedbackRepository()

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
        messages = self.messages_repository.get_conversation_messages(conversation_id)
        if not messages:
            return messages
        message_ids = [m.get("id") for m in messages if m.get("id")]
        if not message_ids:
            return messages

        sources_by_msg: dict[int, list[dict]] = defaultdict(list)
        try:
            source_rows = self.message_documents_repository.get_sources_by_message_ids(message_ids)
            doc_ids = list({s.get("documento_id") for s in source_rows if s.get("documento_id")})
            titles = self.message_documents_repository.get_document_titles(doc_ids) if doc_ids else {}
            for s in source_rows:
                msg_id = s.get("mensaje_id")
                if msg_id is None:
                    continue
                sources_by_msg[msg_id].append(
                    {
                        "document_id": s.get("documento_id"),
                        "document": titles.get(s.get("documento_id")),
                        "page": s.get("page_number"),
                        "similarity_score": s.get("similarity_score", 0.0),
                    }
                )
        except Exception:
            sources_by_msg = defaultdict(list)

        feedback_by_msg: dict[int, dict] = {}
        try:
            fb_rows = self.feedback_repository.get_feedback_by_message_ids(message_ids)
            for f in fb_rows:
                if f.get("message_id") is not None:
                    feedback_by_msg[f["message_id"]] = {"rating": f.get("rating"), "comment": f.get("comment")}
        except Exception:
            feedback_by_msg = {}

        for m in messages:
            mid = m.get("id")
            m["_sources"] = sources_by_msg.get(mid, [])
            m["_rating"] = feedback_by_msg.get(mid, {}).get("rating")
            m["_feedback_comment"] = feedback_by_msg.get(mid, {}).get("comment")
        return messages

    def count_messages(self, conversation_id: int) -> int:
        return self.messages_repository.count_conversation_messages(conversation_id)
