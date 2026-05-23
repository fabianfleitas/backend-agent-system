from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


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
    estado_indexacion: str
    es_version_activa: bool
    total_chunks: int
    fecha_carga: datetime
    fecha_indexacion: Optional[datetime]
    cargado_por_external_auth_id: str


@dataclass
class AuditLog:
    id: int
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
        self._audit_id = 0

        self.conversations: Dict[int, Conversation] = {}
        self.messages: Dict[int, Message] = {}
        self.audios: Dict[int, AudioInteraction] = {}
        self.documents: Dict[int, Document] = {}
        self.document_versions: Dict[int, DocumentVersion] = {}
        self.audit_logs: Dict[int, AuditLog] = {}

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
        )
        self.messages[msg.id] = msg
        conv = self.conversations[conversation_id]
        conv.ultima_interaccion = now
        return msg

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
            estado_indexacion="PENDIENTE",
            es_version_activa=True,
            total_chunks=0,
            fecha_carga=utc_now(),
            fecha_indexacion=None,
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
            version.estado_indexacion = "INDEXADO"
            version.total_chunks = 0
            version.fecha_indexacion = utc_now()
            updated += 1
        return updated

    def list_audit_logs(self) -> List[AuditLog]:
        items = list(self.audit_logs.values())
        items.sort(key=lambda a: a.fecha_evaluacion, reverse=True)
        return items

    def add_audit_log(self, mensaje_id: int, observaciones: Optional[str] = None) -> AuditLog:
        self._audit_id += 1
        log = AuditLog(
            id=self._audit_id,
            mensaje_id=mensaje_id,
            score_fidelidad=None,
            score_relevancia=None,
            score_contexto=None,
            observaciones=observaciones,
            fecha_evaluacion=utc_now(),
        )
        self.audit_logs[log.id] = log
        return log


store = MockStore()
