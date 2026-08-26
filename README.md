# backend-agent-system

Backend FastAPI para un asistente academico institucional. El proyecto ya expone una API modular para conversaciones, chat de texto, chat por voz, documentos, auditoria, usuarios y metricas, con persistencia real parcial y varias integraciones reales activadas por flags.

La regla principal del repositorio sigue siendo esta: distinguir siempre entre el **estado actual implementado** y la **arquitectura objetivo**. No asumir que una ruta existe solo porque la capacidad final ya esta completa.

## Estado actual

- FastAPI como framework principal.
- Factory central en `app/main.py:create_app()`.
- Auth con JWT de Supabase Auth (implementado tras FASE B)
- Aislamiento multi-institución por `institucion_id` (FASE A)
- `app_users.role` deprecado; permisos desde `institucion_miembros.tipo_miembro` / `platform_admins`
- `/me` y `/ready` usan Supabase de forma real.
- Conversaciones, mensajes, documentos, versiones, audio metadata, auditoria, feedback y trazabilidad RAG persisten en Supabase mediante repositories.
- Archivos subidos se guardan en **Supabase Storage** (bucket `documents` / `audio`) con prefijo institucional (`{institucion_id}/documents/`, `{institucion_id}/audio/`); metadatos en Supabase.
- `chat/query` recupera contexto real cuando `EMBEDDINGS_ENABLED=true` y puede generar respuesta real con OpenRouter cuando `LLM_ENABLED=true`.
- `chat/voice` puede transcribir con STT real cuando `STT_ENABLED=true` y sintetizar respuesta con TTS real cuando `TTS_ENABLED=true`.
- `openapi.current.json` generado (`/docs`, `/openapi.json`); contrato actualizado con endpoints de `config`, `platform` y `billing`.
- `FRONTEND_API_INTEGRATION.md` actualizado con contratos de `UserOut` completo (`tipo_miembro`, `is_platform_admin`, `institucion_id`), `MetricsOut` con series/filtros, `Platform` (`/api/platform/*`), `ConfigParam` (GET/PUT) y billing lectura (`/subscription`, `/plan`, `/pagos`, `/comprobantes`).
- Existe una carpeta `tests/` con cobertura en desarrollo para servicios e integraciones criticas.

## Capacidad por flag

- `EMBEDDINGS_ENABLED=true`: activa retrieval real, chunking, embeddings e indexacion.
- `LLM_ENABLED=true`: activa generacion real de respuesta con OpenRouter.
- `LLM_HISTORY_ENABLED=true`: agrega memoria conversacional al prompt, limitada por tokens y cantidad de mensajes.
- `STT_ENABLED=true`: activa transcripcion real del audio.
- `TTS_ENABLED=true`: activa sintesis de audio para la respuesta.

## Requisitos

- Python 3.10+
- Dependencias de `requirements.txt`
- Opcional: proyecto Supabase con tablas en `migrations/001_multi_institution.sql`; esquema completo en `all_tables.json`.

## Instalacion local

Crear y activar un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalar dependencias:

```bash
python3 -m pip install -r requirements.txt
```

Configurar `.env` en la raiz si hace falta ajustar Supabase, OpenRouter, STT, TTS o embeddings.

## Variables de entorno

```env
APP_NAME=backend-agent-system
ENVIRONMENT=local
API_PREFIX=/api

STORAGE_ROOT=storage
STORAGE_AUDIO_DIR=storage/audio
STORAGE_DOCUMENTS_DIR=storage/documents

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_STORAGE_BUCKET_DOCUMENTS=documents
SUPABASE_STORAGE_BUCKET_AUDIO=audio
SUPABASE_JWT_SECRET=  # para validación local del JWT de Supabase Auth

OPENAI_API_KEY=

OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_ENABLED=false
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=512
LLM_HISTORY_ENABLED=true

STT_ENABLED=false
STT_MODEL=x-ai/grok-stt-1.0
STT_RESPONSE_FORMAT=verbose_json

TTS_ENABLED=false
TTS_MODEL=hexgrad/kokoro-82m
TTS_VOICE=ef_dora
TTS_RESPONSE_FORMAT=mp3

EMBEDDINGS_ENABLED=false
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
RETRIEVAL_SIMILARITY_THRESHOLD=0.30
RETRIEVAL_MATCH_COUNT=5
```

Notas:

- `SUPABASE_SECRET_KEY` es alias de `SUPABASE_SERVICE_ROLE_KEY`.
- Si Supabase no esta configurado, `/ready` devuelve `not_ready`.
- Si Supabase no esta configurado, `/me` puede devolver `503`.
- `OPENAI_API_KEY` hoy solo impacta el readiness.

## Ejecutar

```bash
uvicorn app.main:app --reload
```

Documentacion interactiva:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

OpenAPI oficial (`openapi.current.json`) se genera desde `create_app()` con contrato actualizado: auth, multiinstitución, RAG, voz, documents, admin (`config`, `metrics`, `users`), `platform/*` y `billing` lectura.

## Endpoints principales

Globales:

```text
GET /health
GET /ready
GET /me
```

API:

```text
POST   /api/conversations
GET    /api/conversations
GET    /api/conversations/{conversation_id}
DELETE /api/conversations/{conversation_id}
GET    /api/conversations/{conversation_id}/messages

POST   /api/chat/query
POST   /api/chat/voice
GET    /api/chat/audio/{audio_interaction_id}
POST   /api/chat/feedback

POST   /api/admin/documents
GET    /api/admin/documents
GET    /api/admin/documents/{documento_id}
DELETE /api/admin/documents/{documento_id}
POST   /api/admin/documents/{documento_id}/versions
POST   /api/admin/reindex
GET    /api/admin/audit
GET    /api/admin/users
GET    /api/admin/metrics
GET    /api/admin/categories
GET    /api/admin/config
GET    /api/admin/subscription
GET    /api/admin/plan
GET    /api/admin/pagos
GET    /api/admin/comprobantes
GET    /api/platform/institutions
GET    /api/platform/institutions/{id}/members
GET    /api/platform/users
GET    /api/platform/metrics
GET    /api/platform/audit
GET    /api/platform/plans
GET    /api/platform/subscriptions
GET    /api/platform/pagos
GET    /api/platform/comprobantes
```

## Autenticacion con Supabase Auth

El backend valida JWT emitidos por Supabase Auth. El cliente debe enviar:

```http
Authorization: Bearer <jwt>
```

Flujo:
1. `get_auth_context()` extrae `sub` (campo `auth.users.id`) del JWT.
2. Valida `is_active` en `app_users`.
3. Resuelve membresía activa en `institucion_miembros` (`tipo_miembro`, `institucion_id`).
4. Comprueba `platform_admins` (`is_platform_admin`).
5. `app_users.role` está deprecado; no se consulta para permisos institucionales.

Reglas:
- `Authorization: Bearer <jwt>` obligatorio para endpoints de negocio.
- `app_users.role` deprecado; permisos institucionales desde `institucion_miembros.tipo_membro` y `platform_admins.is_platform_admin`.
- `platform_admin`: acceso a `/api/platform/*`; para `/admin/*` requiere membresía institucional.
- Acceso cruzado: 404 si el recurso no pertenece a `auth.institucion_id`.
- Admin institucional: `tipo_miembro` = `ADMIN` o `SECRETARIA` en `institucion_miembros`.
- Superadmin (global): `is_platform_admin = true` en `platform_admins`; sin requerir institución.
- Acceso cruzado: 404 si el recurso no pertenece a `auth.institucion_id`.
- Headers delegados (`X-External-Auth-Id`, `X-User-Type`, etc.) quedan obsoletos.

## Contrato de chat

`POST /api/chat/query` y `POST /api/chat/voice` devuelven:

- `response`
- `sources`
- `audit_id`
- `conversation_id`
- `user_message`
- `assistant_message`

El chat ya no depende de un flujo puramente mock:

- Si hay embeddings habilitados y hay contexto suficiente, se recuperan fragmentos reales.
- Si `LLM_ENABLED=true`, la respuesta puede salir de OpenRouter.
- Si no hay contexto institucional suficiente, el backend aplica el guard de dominio.
- Si el LLM falla, la respuesta degrada de forma controlada y la trazabilidad queda en auditoria.

En voz:

- Si `STT_ENABLED=true`, el audio se transcribe antes de entrar al flujo RAG + LLM.
- Si `TTS_ENABLED=true`, la respuesta se sintetiza y se guarda como metadata de audio.

Para ver el contrato completo del frontend, ejemplos de payloads y comportamiento por flag, usar `FRONTEND_API_INTEGRATION.md`.

## Supabase y modelo de datos

`migrations/001_multi_institution.sql` y `all_tables.json`

- `app_users`
- `conversaciones`
- `mensajes`
- `documentos`
- `documento_versiones`
- `document_chunks`
- `document_embeddings`
- `message_documents`
- `audit_logs`
- `feedback`
- `audio_interactions`
- `pii_mappings`

## Persistencia y storage

Actual:

- Los documentos y audios subidos se escriben en `storage/`.
- Los metadatos y trazabilidad ya se guardan en Supabase.
- Ocultar una conversacion no borra fisicamente el historial.

Objetivo:

- Persistencia completa y consistente en Supabase/PostgreSQL.
- Versionado documental mas robusto.
- Trazabilidad RAG por documento y chunk.
- Auditoria persistente por respuesta generada.
- Storage privado para documentos y audios.

## Prioridades tecnicas

1. Persistencia completa de historial, documentos, auditoria, feedback y audio metadata.
2. Gestion documental con versionado y reindexacion robustos.
3. Pipeline RAG real con chunking, embeddings y recuperacion.
4. Integracion estable con OpenRouter y otros proveedores IA configurables.
5. STT/TTS real para consultas por voz.
6. Workers asincronos para tareas pesadas.
7. Tests automatizados, observabilidad y metricas ampliadas.

## Advertencias de desarrollo

- No reemplazar `create_app()` por una instancia plana de `FastAPI()`.
- No agregar una base de datos nueva ni librerias grandes sin implementar realmente la capacidad asociada.
- No romper el aislamiento por `external_auth_id`.
- No convertir ocultamiento de conversaciones en borrado fisico.
- No asumir que `/ready` valida OpenAI real; hoy solo verifica presencia de key.
- No asumir que los paths de audio/documentos son URLs publicas.
- Mantener separado el codigo de RAG, voz, IA, historial y documentos.

