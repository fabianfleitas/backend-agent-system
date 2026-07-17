# Guia de integracion para Frontend

Este documento resume los cambios que el frontend debe contemplar para consumir correctamente las salidas actuales del backend.

El backend sigue usando persistencia en memoria y varias respuestas mock, pero el contrato HTTP ya expone una estructura mas cercana a la arquitectura objetivo: conversaciones separadas, chat, voz, auditoria, documentos, usuarios y metricas.

## Base URL

Por defecto, todas las rutas de negocio usan el prefijo:

```text
/api
```

Rutas globales fuera de `/api`:

```text
GET /health
GET /ready
GET /me
```

## Headers requeridos

Todos los endpoints de negocio y `/me` dependen de autenticacion delegada por headers.

El frontend debe enviar siempre:

```http
X-External-Auth-Id: <id externo del usuario>
```

Headers opcionales:

```http
X-Auth-Provider: delegated
X-User-Type: ESTUDIANTE | ADMIN | SECRETARIA
X-User-Email: usuario@institucion.edu
```

Reglas importantes:

- Si falta `X-External-Auth-Id`, el backend responde `401`.
- Los endpoints administrativos requieren `X-User-Type: ADMIN` o `X-User-Type: SECRETARIA`.
- `SECRETARIA` se devuelve al frontend como role `STAFF` en las respuestas.
- No usar JWT propio contra este backend mientras siga activa la autenticacion delegada.

## Cambios principales para el frontend

Las rutas de alumno anteriores ya no son el contrato principal. El frontend debe migrar a estos modulos:

```text
/api/conversations
/api/chat
/api/admin
```

Mapeo recomendado:

| Antes | Ahora |
| --- | --- |
| `POST /api/student/query` | `POST /api/chat/query` |
| `POST /api/student/voice-query` | `POST /api/chat/voice` |
| `GET /api/student/history` | `GET /api/conversations` |
| `PATCH /api/student/history/{id}/hide` | `DELETE /api/conversations/{conversation_id}` |
| `GET /api/health` | `GET /health` |

Nota: aunque la ruta use nombres en ingles, algunos campos de respuesta todavia conservan nombres del modelo inicial en espanol, como `conversacion_id`, `rol_mensaje` y `contenido_texto`.

## Formato de paginacion

Los listados paginados responden siempre:

```json
{
  "items": [],
  "pagination": {
    "total": 0,
    "limit": 20,
    "offset": 0
  }
}
```

El frontend debe leer datos desde `items`, no desde la raiz de la respuesta.

Endpoints paginados:

```text
GET /api/conversations
GET /api/admin/documents
GET /api/admin/audit
GET /api/admin/users
```

Query params:

```text
limit: 1..100, default 20
offset: >=0, default 0
```

## Conversaciones

### Crear conversacion

```http
POST /api/conversations
```

Respuesta `201`:

```json
{
  "id": 1,
  "title": "Conversacion 2026-06-12 15:30:00",
  "messages": []
}
```

El frontend debe crear una conversacion antes de enviar mensajes a `/api/chat/query` o `/api/chat/voice`.

### Listar conversaciones

```http
GET /api/conversations?limit=20&offset=0&include_hidden=false
```

Respuesta:

```json
{
  "items": [
    {
      "id": 1,
      "title": "Conversacion 2026-06-12 15:30:00",
      "last_interaction": "2026-06-12T18:30:00.000000Z",
      "message_count": 2
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### Obtener detalle

```http
GET /api/conversations/{conversation_id}
```

Respuesta:

```json
{
  "id": 1,
  "title": "Conversacion 2026-06-12 15:30:00",
  "messages": [
    {
      "id": 1,
      "conversacion_id": 1,
      "rol_mensaje": "USER",
      "contenido_texto": "Consulta del estudiante",
      "proveedor_ia": null,
      "modelo_ia": null,
      "temperatura": null,
      "tokens_input": null,
      "tokens_output": null,
      "tiempo_respuesta_ms": null,
      "fecha_envio": "2026-06-12T18:30:00.000000Z",
      "audit_id": null
    }
  ]
}
```

Roles esperados en mensajes:

```text
USER
ASSISTANT
```

Para renderizar chat:

- Usar `rol_mensaje` para decidir alineacion/estilo.
- Usar `contenido_texto` como texto visible del mensaje.
- Usar `fecha_envio` para orden temporal.
- Los metadatos IA (`proveedor_ia`, `modelo_ia`, tokens, tiempos, `audit_id`) normalmente aparecen solo en mensajes `ASSISTANT`.

### Ocultar conversacion

```http
DELETE /api/conversations/{conversation_id}
```

Esto no borra fisicamente la conversacion; solo la oculta para el usuario.

Respuesta:

```json
{
  "id": 1,
  "title": "Conversacion 2026-06-12 15:30:00",
  "last_interaction": "2026-06-12T18:35:00.000000Z",
  "message_count": 2
}
```

Para volver a listar conversaciones ocultas:

```http
GET /api/conversations?include_hidden=true
```

## Chat de texto

```http
POST /api/chat/query
Content-Type: application/json
```

Body:

```json
{
  "conversation_id": 1,
  "message": "Cuales son los requisitos para regularizar una materia?"
}
```

Respuesta:

```json
{
  "response": "MOCK: Recibi tu consulta institucional: ...",
  "conversation_id": 1,
  "sources": [
    {
      "document_id": 1,
      "document": "Reglamento Academico.pdf",
      "page": 12,
      "similarity_score": 0.92
    }
  ],
  "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1",
  "user_message": {
    "id": 10,
    "conversacion_id": 1,
    "rol_mensaje": "USER",
    "contenido_texto": "Cuales son los requisitos para regularizar una materia?",
    "proveedor_ia": null,
    "modelo_ia": null,
    "temperatura": null,
    "tokens_input": null,
    "tokens_output": null,
    "tiempo_respuesta_ms": null,
    "fecha_envio": "2026-06-12T18:30:00.000000Z",
    "audit_id": null
  },
  "assistant_message": {
    "id": 11,
    "conversacion_id": 1,
    "rol_mensaje": "ASSISTANT",
    "contenido_texto": "MOCK: Recibi tu consulta institucional: ...",
    "proveedor_ia": "OpenRouter",
    "modelo_ia": "mock",
    "temperatura": 0.2,
    "tokens_input": 8,
    "tokens_output": 10,
    "tiempo_respuesta_ms": 0.0,
    "fecha_envio": "2026-06-12T18:30:01.000000Z",
    "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1"
  }
}
```

Consideraciones para UI:

- Mostrar `response` como respuesta inmediata del asistente.
- Mostrar `sources` como fuentes/citas cuando existan.
- Guardar `audit_id` si luego se enviara feedback.
- Usar `conversation_id`, `user_message` y `assistant_message` para actualizar el store inmediatamente sin esperar un refresh del historial.
- Despues de enviar un mensaje, opcionalmente se puede refrescar `GET /api/conversations/{conversation_id}` para reconciliar historial completo.
- Si `conversation_id` no pertenece al usuario autenticado, el backend responde `404`.

## Chat por voz

```http
POST /api/chat/voice?conversation_id=1
Content-Type: multipart/form-data
```

Form data:

```text
audio: File
```

Respuesta:

```json
{
  "response": "MOCK: respuesta simulada basada en reglamentos institucionales...",
  "conversation_id": 1,
  "sources": [
    {
      "document_id": 1,
      "document": "Reglamento Academico.pdf",
      "page": 12,
      "similarity_score": 0.92
    }
  ],
  "transcription": "MOCK: transcripcion simulada del audio",
  "audio_interaction": {
    "id": 1,
    "mensaje_id": 2,
    "ruta_audio_original": "audio/archivo.wav",
    "ruta_audio_respuesta": "audio/respuesta.wav",
    "transcripcion": "MOCK: transcripcion simulada del audio",
    "duracion_segundos": null,
    "formato_audio": "audio/wav",
    "tamano_bytes": 12345,
    "fecha_creacion": "2026-06-12T18:30:00.000000Z"
  },
  "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1",
  "user_message": {
    "id": 2,
    "conversacion_id": 1,
    "rol_mensaje": "USER",
    "contenido_texto": "MOCK: transcripcion simulada del audio",
    "proveedor_ia": null,
    "modelo_ia": null,
    "temperatura": null,
    "tokens_input": null,
    "tokens_output": null,
    "tiempo_respuesta_ms": null,
    "fecha_envio": "2026-06-12T18:30:00.000000Z",
    "audit_id": null
  },
  "assistant_message": {
    "id": 3,
    "conversacion_id": 1,
    "rol_mensaje": "ASSISTANT",
    "contenido_texto": "MOCK: respuesta simulada basada en reglamentos institucionales...",
    "proveedor_ia": "OpenRouter",
    "modelo_ia": "mock",
    "temperatura": 0.2,
    "tokens_input": 6,
    "tokens_output": 10,
    "tiempo_respuesta_ms": 0.0,
    "fecha_envio": "2026-06-12T18:30:01.000000Z",
    "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1"
  }
}
```

Consideraciones para UI:

- `transcription` es el texto transcripto que puede mostrarse como mensaje del usuario.
- `response` es el texto de respuesta del asistente.
- Usar `conversation_id`, `user_message` y `assistant_message` para actualizar el store inmediatamente despues del envio.
- `ruta_audio_respuesta` existe como metadata en Supabase Storage, pero hoy el archivo generado esta vacio porque TTS real aun no esta implementado.
- No asumir que `ruta_audio_original` o `ruta_audio_respuesta` son URLs publicas descargables; actualmente son rutas internas de storage.

## Feedback de respuestas

```http
POST /api/chat/feedback
Content-Type: application/json
```

Body:

```json
{
  "message_id": 2,
  "rating": 5,
  "comment": "Respuesta util",
  "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1"
}
```

Respuesta:

```json
{
  "id": 1,
  "message_id": 2,
  "rating": 5,
  "comment": "Respuesta util",
  "audit_id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1",
  "created_at": "2026-06-12T18:31:00.000000Z"
}
```

Validaciones:

- `rating` debe estar entre `1` y `5`.
- `audit_id` debe ser UUID.
- El backend valida ownership del `message_id`; si no pertenece al usuario autenticado responde `404`.

## Validacion end-to-end recomendada

Secuencia sugerida para validar integracion con el modulo de estudiante:

1. Obtener o crear identidad delegada del alumno con `X-External-Auth-Id`.
2. Crear conversacion con `POST /api/conversations`.
3. Enviar texto con `POST /api/chat/query` y actualizar el store usando `conversation_id`, `user_message` y `assistant_message`.
4. Enviar voz con `POST /api/chat/voice?conversation_id=...` usando `multipart/form-data`.
5. Refrescar historial con `GET /api/conversations/{conversation_id}` para reconciliar mensajes persistidos.
6. Listar conversaciones con `GET /api/conversations?include_hidden=false`.
7. Enviar feedback sobre el `assistant_message.id` recibido.

Resultados esperados:

- La conversacion debe quedar persistida en Supabase.
- Los mensajes `USER` y `ASSISTANT` deben aparecer en detalle de conversacion.
- `audit_id` debe existir en respuestas del asistente.
- En voz, `audio_interaction` debe registrar rutas internas en bucket `audio`.
- Si el alumno consulta una conversacion ajena, el backend debe responder `404`.

## Usuario actual

```http
GET /me
```

Respuesta:

```json
{
  "external_auth_id": "user-123",
  "email": "usuario@institucion.edu",
  "role": "STUDENT",
  "created_at": "2026-06-12T18:30:00.000000Z",
  "updated_at": "2026-06-12T18:30:00.000000Z"
}
```

Roles devueltos:

```text
STUDENT
STAFF
ADMIN
```

## Administracion

Todos los endpoints de esta seccion requieren:

```http
X-User-Type: ADMIN
```

o:

```http
X-User-Type: SECRETARIA
```

### Subir documento

```http
POST /api/admin/documents
Content-Type: multipart/form-data
```

Form data:

```text
file: File
titulo: string
descripcion: string opcional
categoria_id: number opcional
codigo_documento: string opcional
```

Respuesta:

```json
{
  "document": {
    "id": 1,
    "categoria_id": null,
    "codigo_documento": "REG-001",
    "titulo": "Reglamento Academico",
    "descripcion": "Documento institucional",
    "activo": true,
    "fecha_creacion": "2026-06-12T18:30:00.000000Z",
    "version_activa": {
      "id": 1,
      "documento_id": 1,
      "numero_version": 1,
      "ruta_archivo": "storage/documents/archivo.pdf",
      "status": "PENDING",
      "es_version_activa": true,
      "total_chunks": 0,
      "embedding_model": null,
      "fecha_carga": "2026-06-12T18:30:00.000000Z",
      "indexed_at": null,
      "cargado_por_external_auth_id": "admin-123"
    }
  },
  "version": {
    "id": 1,
    "documento_id": 1,
    "numero_version": 1,
    "ruta_archivo": "storage/documents/archivo.pdf",
    "status": "PENDING",
    "es_version_activa": true,
    "total_chunks": 0,
    "embedding_model": null,
    "fecha_carga": "2026-06-12T18:30:00.000000Z",
    "indexed_at": null,
    "cargado_por_external_auth_id": "admin-123"
  }
}
```

Estados posibles de documentos:

```text
PENDING
PROCESSING
READY
FAILED
```

Hoy la subida deja la version en `PENDING`.

### Listar documentos

```http
GET /api/admin/documents?limit=20&offset=0
```

Respuesta paginada con `DocumentOut` dentro de `items`.

### Ver detalle de documento

```http
GET /api/admin/documents/{documento_id}
```

Respuesta con todas las versiones del documento:

```json
{
  "id": 1,
  "categoria_id": 1,
  "codigo_documento": "REG-001",
  "titulo": "Reglamento Academico",
  "descripcion": "Documento institucional",
  "activo": true,
  "fecha_creacion": "2026-06-12T18:30:00.000000Z",
  "versiones": [
    {
      "id": 2,
      "documento_id": 1,
      "numero_version": 2,
      "ruta_archivo": "storage/documents/abc123.pdf",
      "status": "PENDING",
      "es_version_activa": true,
      "total_chunks": 0,
      "embedding_model": null,
      "fecha_carga": "2026-06-13T10:30:00.000000Z",
      "indexed_at": null,
      "cargado_por_external_auth_id": "admin-123"
    },
    {
      "id": 1,
      "documento_id": 1,
      "numero_version": 1,
      "ruta_archivo": "storage/documents/def456.pdf",
      "status": "READY",
      "es_version_activa": false,
      "total_chunks": 0,
      "embedding_model": null,
      "fecha_carga": "2026-06-12T18:30:00.000000Z",
      "indexed_at": "2026-06-12T18:35:00.000000Z",
      "cargado_por_external_auth_id": "admin-123"
    }
  ]
}
```

El campo `versiones` lista todas las versiones del documento ordenadas por `numero_version` descendente. La version activa se identifica con `es_version_activa: true`.

### Subir nueva version de documento

```http
POST /api/admin/documents/{documento_id}/versions
Content-Type: multipart/form-data
```

Form data:

```text
file: File
```

Respuesta `201`:

```json
{
  "document": {
    "id": 1,
    "categoria_id": 1,
    "codigo_documento": "REG-001",
    "titulo": "Reglamento Academico",
    "descripcion": "Documento institucional",
    "activo": true,
    "fecha_creacion": "2026-06-12T18:30:00.000000Z",
    "version_activa": {
      "id": 2,
      "documento_id": 1,
      "numero_version": 2,
      "ruta_archivo": "storage/documents/abc123.pdf",
      "status": "PENDING",
      "es_version_activa": true,
      "total_chunks": 0,
      "embedding_model": null,
      "fecha_carga": "2026-06-13T10:30:00.000000Z",
      "indexed_at": null,
      "cargado_por_external_auth_id": "admin-123"
    }
  },
  "version": {
    "id": 2,
    "documento_id": 1,
    "numero_version": 2,
    "ruta_archivo": "storage/documents/abc123.pdf",
    "status": "PENDING",
    "es_version_activa": true,
    "total_chunks": 0,
    "embedding_model": null,
    "fecha_carga": "2026-06-13T10:30:00.000000Z",
    "indexed_at": null,
    "cargado_por_external_auth_id": "admin-123"
  }
}
```

Al subir una nueva version, el sistema automaticamente:
- Incrementa `numero_version` tomando la maxima existente + 1
- Desactiva todas las versiones anteriores (`es_version_activa = false`)
- Marca la nueva version como activa (`es_version_activa = true`)
- La nueva version queda en estado `PENDING` hasta ser indexada

### Desactivar documento

```http
DELETE /api/admin/documents/{documento_id}
```

Esto no borra fisicamente el documento ni sus versiones; solo cambia `activo` a `false`.

Respuesta:

```json
{
  "id": 1,
  "categoria_id": 1,
  "codigo_documento": "REG-001",
  "titulo": "Reglamento Academico",
  "descripcion": "Documento institucional",
  "activo": false,
  "fecha_creacion": "2026-06-12T18:30:00.000000Z",
  "version_activa": {
    "id": 2,
    "documento_id": 1,
    "numero_version": 2,
    "ruta_archivo": "storage/documents/abc123.pdf",
    "status": "READY",
    "es_version_activa": true,
    "total_chunks": 0,
    "embedding_model": null,
    "fecha_carga": "2026-06-13T10:30:00.000000Z",
    "indexed_at": "2026-06-13T10:35:00.000000Z",
    "cargado_por_external_auth_id": "admin-123"
  }
}
```

Si el documento no existe o ya esta inactivo, responde `404`.

### Reindexar documentos

```http
POST /api/admin/reindex
Content-Type: application/json
```

Body para reindexar todo:

```json
{
  "documento_id": null
}
```

Body para reindexar un documento:

```json
{
  "documento_id": 1
}
```

Respuesta:

```json
{
  "updated_versions": 1
}
```

En la implementacion actual, reindexar solo cambia metadata mock: marca versiones como `READY`, setea `indexed_at` y mantiene `total_chunks` en `0`.

### Auditoria

```http
GET /api/admin/audit?limit=20&offset=0
```

Respuesta:

```json
{
  "items": [
    {
      "id": "6b0f9f86-8f2c-4c49-9d3d-3a9f5bb0a2d1",
      "mensaje_id": 2,
      "score_fidelidad": null,
      "score_relevancia": null,
      "score_contexto": null,
      "observaciones": "MOCK: sin evaluacion automatica",
      "fecha_evaluacion": "2026-06-12T18:31:00.000000Z"
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### Usuarios

```http
GET /api/admin/users?limit=20&offset=0
```

Respuesta paginada con usuarios:

```json
{
  "items": [
    {
      "external_auth_id": "user-123",
      "email": "usuario@institucion.edu",
      "role": "STUDENT",
      "created_at": "2026-06-12T18:30:00.000000Z",
      "updated_at": "2026-06-12T18:30:00.000000Z"
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### Metricas

```http
GET /api/admin/metrics
```

Respuesta:

```json
{
  "total_queries": 2,
  "total_conversations": 1,
  "total_documents": 1,
  "total_feedbacks": 1,
  "avg_response_time": 0.03,
  "avg_fidelity": 0.0,
  "avg_relevance": 0.0,
  "system_status": "healthy"
}
```

Nota: en el store actual `system_status` puede venir por default del schema aunque no lo devuelva explicitamente el servicio.

## Health y readiness

```http
GET /health
```

Respuesta:

```json
{
  "status": "ok"
}
```

```http
GET /ready
```

Respuesta:

```json
{
  "status": "ready",
  "services": {
    "database": true,
    "openai": true,
    "vector_store": true,
    "storage": true
  }
}
```

Importante: `database`, `openai` y `vector_store` todavia son flags mock. No usarlos como prueba real de disponibilidad de esos servicios.

## Errores esperados

Formato comun de error FastAPI:

```json
{
  "detail": "Mensaje de error"
}
```

Casos principales:

| Status | Caso |
| --- | --- |
| `401` | Falta `X-External-Auth-Id` |
| `403` | Usuario sin rol admin/staff en endpoints `/api/admin` |
| `404` | Conversacion inexistente o perteneciente a otro usuario |
| `422` | Body invalido, query params fuera de rango o multipart incompleto |

## Checklist de cambios en frontend

- Enviar `X-External-Auth-Id` en todas las llamadas al backend.
- Enviar `X-User-Type` segun sesion: `ESTUDIANTE`, `ADMIN` o `SECRETARIA`.
- Crear conversacion con `POST /api/conversations` antes del primer mensaje.
- Reemplazar historial plano por consumo de `GET /api/conversations` y `GET /api/conversations/{id}`.
- Leer listados desde `response.items` y paginacion desde `response.pagination`.
- Mapear mensajes usando `rol_mensaje` y `contenido_texto`, no `role` ni `content`.
- Enviar chat de texto a `POST /api/chat/query` con `conversation_id`.
- Enviar audio a `POST /api/chat/voice?conversation_id=<id>` como `multipart/form-data`.
- Mostrar fuentes desde `sources[]` cuando existan.
- Guardar `audit_id` para feedback y trazabilidad.
- Implementar feedback con `POST /api/chat/feedback`.
- Tratar `DELETE /api/conversations/{id}` como ocultar conversacion, no como borrado permanente.
- No intentar reproducir `ruta_audio_respuesta` como URL publica hasta que exista endpoint de descarga/serving de audio.
- En admin, subir documentos con `multipart/form-data` y mostrar estado de version activa (`PENDING`, `PROCESSING`, `READY`, `FAILED`).
- En admin, usar `GET /api/admin/documents/{id}` para ver el detalle y todas las versiones de un documento.
- En admin, usar `DELETE /api/admin/documents/{id}` para desactivar (soft-delete) un documento.
- Usar `/health`, no `/api/health`.

## Contratos TypeScript sugeridos

```ts
type UserRole = "STUDENT" | "STAFF" | "ADMIN";
type MessageRole = "USER" | "ASSISTANT";
type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

type PaginationMeta = {
  total: number;
  limit: number;
  offset: number;
};

type PaginatedResponse<T> = {
  items: T[];
  pagination: PaginationMeta;
};

type ConversationSummary = {
  id: number;
  title: string;
  last_interaction: string;
  message_count: number;
};

type Message = {
  id: number;
  conversacion_id: number;
  rol_mensaje: MessageRole;
  contenido_texto: string;
  proveedor_ia: string | null;
  modelo_ia: string | null;
  temperatura: number | null;
  tokens_input: number | null;
  tokens_output: number | null;
  tiempo_respuesta_ms: number | null;
  fecha_envio: string;
  audit_id: string | null;
};

type ConversationDetail = {
  id: number;
  title: string;
  messages: Message[];
};

type Source = {
  document_id: number;
  document: string;
  page: number;
  similarity_score: number;
};

type ChatQueryResponse = {
  response: string;
  sources: Source[];
  audit_id: string;
};

type AudioInteraction = {
  id: number;
  mensaje_id: number;
  ruta_audio_original: string;
  ruta_audio_respuesta: string | null;
  transcripcion: string | null;
  duracion_segundos: number | null;
  formato_audio: string | null;
  tamano_bytes: number | null;
  fecha_creacion: string;
};

type ChatVoiceResponse = ChatQueryResponse & {
  transcription: string;
  audio_interaction: AudioInteraction;
};

type DocumentVersion = {
  id: number;
  documento_id: number;
  numero_version: number;
  ruta_archivo: string;
  status: DocumentStatus;
  es_version_activa: boolean;
  total_chunks: number;
  embedding_model: string | null;
  fecha_carga: string;
  indexed_at: string | null;
  cargado_por_external_auth_id: string;
};

type DocumentOut = {
  id: number;
  categoria_id: number | null;
  codigo_documento: string | null;
  titulo: string;
  descripcion: string | null;
  activo: boolean;
  fecha_creacion: string;
  version_activa: DocumentVersion | null;
};

type DocumentDetail = {
  id: number;
  categoria_id: number | null;
  codigo_documento: string | null;
  titulo: string;
  descripcion: string | null;
  activo: boolean;
  fecha_creacion: string;
  versiones: DocumentVersion[];
};

type UploadVersionResponse = {
  document: DocumentOut;
  version: DocumentVersion;
};
```
