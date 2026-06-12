from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class User:
    external_auth_id: str
    auth_provider: str
    tipo_usuario: str
    nombre: Optional[str]
    apellido: Optional[str]
    correo: Optional[str]
    activo: bool
    fecha_creacion: datetime


@dataclass
class Conversation:
    id: int
    usuario_external_auth_id: str
    titulo: str
    oculto_usuario: bool
    estado: str
    fecha_inicio: datetime
    ultima_interaccion: datetime


@dataclass
class Message:
    id: int
    conversacion_id: int
    rol_mensaje: str
    contenido_texto: str
    proveedor_ia: Optional[str]
    modelo_ia: Optional[str]
    temperatura: Optional[float]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    tiempo_respuesta_ms: Optional[float]
    fecha_envio: datetime
    audit_id: Optional[str] = None


@dataclass
class AudioInteraction:
    id: int
    mensaje_id: int
    ruta_audio_original: str
    ruta_audio_respuesta: Optional[str]
    transcripcion: Optional[str]
    duracion_segundos: Optional[float]
    formato_audio: Optional[str]
    tamano_bytes: Optional[int]
    fecha_creacion: datetime


@dataclass
class Document:
    id: int
    categoria_id: Optional[int]
    codigo_documento: Optional[str]
    titulo: str
    descripcion: Optional[str]
    activo: bool
    fecha_creacion: datetime
    version_activa_id: Optional[int]


@dataclass
class DocumentVersion:
    id: int
    documento_id: int
    numero_version: int
    ruta_archivo: str
    status: str  # DocumentStatus value
    es_version_activa: bool
    total_chunks: int
    embedding_model: Optional[str]
    fecha_carga: datetime
    indexed_at: Optional[datetime]
    cargado_por_external_auth_id: str


@dataclass
class Feedback:
    id: int
    message_id: int
    rating: int
    comment: Optional[str]
    audit_id: str
    created_at: datetime


@dataclass
class AuditLog:
    id: str  # UUID as string
    mensaje_id: int
    score_fidelidad: Optional[float]
    score_relevancia: Optional[float]
    score_contexto: Optional[float]
    observaciones: Optional[str]
    fecha_evaluacion: datetime


class MockStore:
    def __init__(self) -> None:
        self._conversation_id = 0
        self._message_id = 0
        self._audio_id = 0
        self._document_id = 0
        self._document_version_id = 0
        self._audit_id_counter = 0
        self._feedback_id = 0

        self.users: Dict[str, User] = {}  # keyed by external_auth_id
        self.conversations: Dict[int, Conversation] = {}
        self.messages: Dict[int, Message] = {}
        self.audios: Dict[int, AudioInteraction] = {}
        self.documents: Dict[int, Document] = {}
        self.document_versions: Dict[int, DocumentVersion] = {}
        self.audit_logs: Dict[str, AuditLog] = {}  # keyed by UUID string
        self.feedbacks: Dict[int, Feedback] = {}

    # ── User ──────────────────────────────────────────────

    def get_or_create_user(
        self,
        external_auth_id: str,
        auth_provider: str,
        tipo_usuario: str,
        correo: Optional[str] = None,
    ) -> User:
        existing = self.users.get(external_auth_id)
        if existing:
            return existing
        user = User(
            external_auth_id=external_auth_id,
            auth_provider=auth_provider,
            tipo_usuario=tipo_usuario,
            nombre=None,
            apellido=None,
            correo=correo,
            activo=True,
            fecha_creacion=utc_now(),
        )
        self.users[external_auth_id] = user
        return user

    def list_users(self) -> List[User]:
        return list(self.users.values())

    # ── Conversation ──────────────────────────────────────

    def create_conversation(self, external_auth_id: str, titulo: str) -> Conversation:
        self._conversation_id += 1
        now = utc_now()
        conv = Conversation(
            id=self._conversation_id,
            usuario_external_auth_id=external_auth_id,
            titulo=titulo,
            oculto_usuario=False,
            estado="ACTIVA",
            fecha_inicio=now,
            ultima_interaccion=now,
        )
        self.conversations[conv.id] = conv
        return conv

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        return self.conversations.get(conversation_id)

    def list_conversations(
        self, external_auth_id: str, include_hidden: bool
    ) -> List[Conversation]:
        items = [
            c for c in self.conversations.values() if c.usuario_external_auth_id == external_auth_id
        ]
        if not include_hidden:
            items = [c for c in items if not c.oculto_usuario]
        items.sort(key=lambda c: c.ultima_interaccion, reverse=True)
        return items

    def hide_conversation(self, external_auth_id: str, conversation_id: int) -> Conversation:
        conv = self.conversations.get(conversation_id)
        if not conv or conv.usuario_external_auth_id != external_auth_id:
            raise KeyError("conversation_not_found")
        conv.oculto_usuario = True
        conv.ultima_interaccion = utc_now()
        return conv

    def get_message_count(self, conversation_id: int) -> int:
        return sum(1 for m in self.messages.values() if m.conversacion_id == conversation_id)

    # ── Message ───────────────────────────────────────────

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        proveedor_ia: Optional[str] = None,
        modelo_ia: Optional[str] = None,
        temperatura: Optional[float] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        tiempo_respuesta_ms: Optional[float] = None,
        audit_id: Optional[str] = None,
    ) -> Message:
        self._message_id += 1
        now = utc_now()
        msg = Message(
            id=self._message_id,
            conversacion_id=conversation_id,
            rol_mensaje=role,
            contenido_texto=content,
            proveedor_ia=proveedor_ia,
            modelo_ia=modelo_ia,
            temperatura=temperatura,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=tiempo_respuesta_ms,
            fecha_envio=now,
            audit_id=audit_id,
        )
        self.messages[msg.id] = msg
        conv = self.conversations[conversation_id]
        conv.ultima_interaccion = now
        return msg

    def get_conversation_messages(self, conversation_id: int) -> List[Message]:
        items = [m for m in self.messages.values() if m.conversacion_id == conversation_id]
        items.sort(key=lambda m: m.fecha_envio)
        return items

    # ── Audio ─────────────────────────────────────────────

    def add_audio_interaction(
        self,
        mensaje_id: int,
        ruta_audio_original: str,
        ruta_audio_respuesta: Optional[str],
        transcripcion: Optional[str],
        formato_audio: Optional[str],
        tamano_bytes: Optional[int],
        duracion_segundos: Optional[float] = None,
    ) -> AudioInteraction:
        self._audio_id += 1
        audio = AudioInteraction(
            id=self._audio_id,
            mensaje_id=mensaje_id,
            ruta_audio_original=ruta_audio_original,
            ruta_audio_respuesta=ruta_audio_respuesta,
            transcripcion=transcripcion,
            duracion_segundos=duracion_segundos,
            formato_audio=formato_audio,
            tamano_bytes=tamano_bytes,
            fecha_creacion=utc_now(),
        )
        self.audios[audio.id] = audio
        return audio

    # ── Document ──────────────────────────────────────────

    def create_document(
        self,
        categoria_id: Optional[int],
        codigo_documento: Optional[str],
        titulo: str,
        descripcion: Optional[str],
        cargado_por_external_auth_id: str,
        ruta_archivo: str,
    ) -> Tuple[Document, DocumentVersion]:
        self._document_id += 1
        now = utc_now()
        doc = Document(
            id=self._document_id,
            categoria_id=categoria_id,
            codigo_documento=codigo_documento,
            titulo=titulo,
            descripcion=descripcion,
            activo=True,
            fecha_creacion=now,
            version_activa_id=None,
        )
        self.documents[doc.id] = doc

        version = self.create_document_version(
            documento_id=doc.id,
            ruta_archivo=ruta_archivo,
            cargado_por_external_auth_id=cargado_por_external_auth_id,
        )
        doc.version_activa_id = version.id
        return doc, version

    def create_document_version(
        self,
        documento_id: int,
        ruta_archivo: str,
        cargado_por_external_auth_id: str,
    ) -> DocumentVersion:
        existing_versions = [
            v for v in self.document_versions.values() if v.documento_id == documento_id
        ]
        numero_version = (max((v.numero_version for v in existing_versions), default=0) + 1) if existing_versions else 1

        self._document_version_id += 1
        version = DocumentVersion(
            id=self._document_version_id,
            documento_id=documento_id,
            numero_version=numero_version,
            ruta_archivo=ruta_archivo,
            status="PENDING",
            es_version_activa=True,
            total_chunks=0,
            embedding_model=None,
            fecha_carga=utc_now(),
            indexed_at=None,
            cargado_por_external_auth_id=cargado_por_external_auth_id,
        )

        for v in existing_versions:
            v.es_version_activa = False

        self.document_versions[version.id] = version
        doc = self.documents[documento_id]
        doc.version_activa_id = version.id
        return version

    def list_documents(self) -> List[Tuple[Document, Optional[DocumentVersion]]]:
        items: List[Tuple[Document, Optional[DocumentVersion]]] = []
        for doc in self.documents.values():
            version = self.document_versions.get(doc.version_activa_id) if doc.version_activa_id else None
            items.append((doc, version))
        items.sort(key=lambda x: x[0].fecha_creacion, reverse=True)
        return items

    def reindex(self, documento_id: Optional[int]) -> int:
        updated = 0
        for version in self.document_versions.values():
            if documento_id is not None and version.documento_id != documento_id:
                continue
            version.status = "READY"
            version.total_chunks = 0
            version.indexed_at = utc_now()
            updated += 1
        return updated

    # ── Audit ─────────────────────────────────────────────

    def add_audit_log(self, mensaje_id: int, observaciones: Optional[str] = None) -> AuditLog:
        log_id = str(_uuid.uuid4())
        log = AuditLog(
            id=log_id,
            mensaje_id=mensaje_id,
            score_fidelidad=None,
            score_relevancia=None,
            score_contexto=None,
            observaciones=observaciones,
            fecha_evaluacion=utc_now(),
        )
        self.audit_logs[log.id] = log
        return log

    def list_audit_logs(self) -> List[AuditLog]:
        items = list(self.audit_logs.values())
        items.sort(key=lambda a: a.fecha_evaluacion, reverse=True)
        return items

    # ── Feedback ──────────────────────────────────────────

    def add_feedback(
        self,
        message_id: int,
        rating: int,
        comment: Optional[str],
        audit_id: str,
    ) -> Feedback:
        self._feedback_id += 1
        fb = Feedback(
            id=self._feedback_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
            audit_id=audit_id,
            created_at=utc_now(),
        )
        self.feedbacks[fb.id] = fb
        return fb

    def list_feedbacks(self) -> List[Feedback]:
        items = list(self.feedbacks.values())
        items.sort(key=lambda f: f.created_at, reverse=True)
        return items

    # ── Metrics ───────────────────────────────────────────

    def get_metrics(self) -> dict:
        all_messages = list(self.messages.values())
        all_conversations = list(self.conversations.values())
        all_documents = list(self.documents.values())
        all_feedbacks = list(self.feedbacks.values())
        all_audit_logs = list(self.audit_logs.values())

        total_queries = len(all_messages)
        total_conversations = len(all_conversations)
        total_documents = len(all_documents)
        total_feedbacks = len(all_feedbacks)

        response_times = [
            m.tiempo_respuesta_ms
            for m in all_messages
            if m.tiempo_respuesta_ms is not None and m.rol_mensaje == "ASSISTANT"
        ]
        avg_response_time = (sum(response_times) / len(response_times)) if response_times else 0.0

        fidelities = [a.score_fidelidad for a in all_audit_logs if a.score_fidelidad is not None]
        avg_fidelity = (sum(fidelities) / len(fidelities)) if fidelities else 0.0

        relevances = [a.score_relevancia for a in all_audit_logs if a.score_relevancia is not None]
        avg_relevance = (sum(relevances) / len(relevances)) if relevances else 0.0

        return {
            "total_queries": total_queries,
            "total_conversations": total_conversations,
            "total_documents": total_documents,
            "total_feedbacks": total_feedbacks,
            "avg_response_time": round(avg_response_time, 2),
            "avg_fidelity": round(avg_fidelity, 4),
            "avg_relevance": round(avg_relevance, 4),
        }


store = MockStore()
