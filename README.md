# backend-agent-system

Backend FastAPI para un asistente academico institucional con conversacion, voz, gestion documental, auditoria y preparacion para RAG.

El proyecto esta en una etapa de transicion: ya expone una API modular para chat, conversaciones y administracion, pero varias capacidades centrales todavia son mocks o persistencia parcial. No asumir que una ruta existente implica que la capacidad final ya esta implementada.

## Arquitectura

### Arquitectura documentada (objetivo)

```text
Usuario
  ↓
Frontend React
  ↓
FastAPI Middleware
  ↓
Anonimización PII
  ↓
RAG
  ↓
LLM
  ↓
Respuesta
  ↓
TTS
```

### Arquitectura actual (implementado)

```text
Usuario
  ↓
Frontend React
  ↓
FastAPI
  ↓
Mock response — Supabase (solo /me y /ready)
```

### Brecha

La ruta completa de anonimizacion, RAG, LLM y TTS aun no esta implementada.
FastAPI expone la API pero responde con datos mock; la unica conexion real a
Supabase esta en los endpoints `/me` y `/ready`.

## Estado actual

Implementado:

- API REST con FastAPI.
- Factory principal en `app/main.py:create_app()`.
- Configuracion con `pydantic-settings` desde `.env`.
- Auth delegada por headers externos.
- Rutas para conversaciones, chat de texto, chat de voz, feedback, documentos, auditoria, usuarios y metricas.
- Persistencia real mediante Supabase para conversaciones, mensajes, documentos, versiones, audios, auditoria y feedback.
- Persistencia real parcial de usuarios con Supabase en `/me`.
- Readiness parcial contra Supabase en `/ready`.
- Guardado local de archivos subidos en `storage/`.
- Esquema SQL objetivo en `tables.sql`.
- Documento de contrato para frontend en `FRONTEND_API_INTEGRATION.md`.

No implementado realmente todavia:

- Middleware de anonimizacion PII.
- RAG real.
- Embeddings reales.
- Recuperacion semantica real.
- OpenRouter u otro proveedor IA real en el flujo de chat.
- STT/TTS real para voz.
- Workers asincronos con Celery/Redis.
- Persistencia real completa de conversaciones, mensajes, documentos, auditoria, feedback y audios.
- Tests automatizados.

## Requisitos

- Python 3.10+
- Dependencias de `requirements.txt`
- Opcional: proyecto Supabase con las tablas de `tables.sql`

Dependencias principales:

```text
fastapi
uvicorn[standard]
python-multipart
pydantic-settings
supabase
```

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

Crear un `.env` en la raiz si se necesita configurar Supabase u otras variables.

## Variables de entorno

Valores soportados:

```env
APP_NAME=backend-agent-system
ENVIRONMENT=local
API_PREFIX=/api

STORAGE_ROOT=storage
STORAGE_AUDIO_DIR=storage/audio
STORAGE_DOCUMENTS_DIR=storage/documents

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET_DOCUMENTS=documents
SUPABASE_STORAGE_BUCKET_AUDIO=audio

OPENAI_API_KEY=
```

Tambien se acepta `SUPABASE_SECRET_KEY` como alias de `SUPABASE_SERVICE_ROLE_KEY`.

Notas:

- Si Supabase no esta configurado, `/ready` devuelve `not_ready`.
- Si Supabase no esta configurado, `/me` puede responder `503` porque intenta persistir/leer el usuario real.
- El chat, conversaciones, documentos, auditoria y feedback usan Supabase mediante repositories.
- `OPENAI_API_KEY` solo impacta el flag de readiness; no hay flujo IA real todavia.

## Ejecutar

```bash
uvicorn app.main:app --reload
```

Documentacion interactiva:

```text
http://127.0.0.1:8000/docs
```

Health:

```text
GET /health
```

Readiness:

```text
GET /ready
```

## Autenticacion delegada

El backend no emite JWT propio. Los endpoints de negocio dependen de headers delegados:

```http
X-External-Auth-Id: <id externo obligatorio>
X-Auth-Provider: delegated
X-User-Type: ESTUDIANTE | ADMIN | SECRETARIA
X-User-Email: usuario@institucion.edu
```

Reglas:

- `X-External-Auth-Id` es obligatorio.
- `X-Auth-Provider` es opcional; por defecto es `delegated`.
- `X-User-Type` por defecto es `ESTUDIANTE`.
- Endpoints administrativos requieren `ADMIN` o `SECRETARIA`.
- `SECRETARIA` se mapea como `STAFF` en las respuestas de usuario persistidas.

La extraccion del contexto vive en `app/core/security.py:get_auth_context()`.

## API actual

Rutas globales:

```text
GET /health
GET /ready
GET /me
```

Rutas bajo `/api`:

```text
POST   /api/conversations
GET    /api/conversations
GET    /api/conversations/{conversation_id}
DELETE /api/conversations/{conversation_id}
GET    /api/conversations/{conversation_id}/messages

POST   /api/chat/query
POST   /api/chat/voice
POST   /api/chat/feedback

POST   /api/admin/documents
GET    /api/admin/documents
POST   /api/admin/reindex
GET    /api/admin/audit
GET    /api/admin/users
GET    /api/admin/metrics
```

Para el contrato de frontend, ejemplos de payloads y tipos sugeridos, ver:

```text
FRONTEND_API_INTEGRATION.md
```

## Flujo basico de chat

1. Crear una conversacion:

```http
POST /api/conversations
```

2. Enviar un mensaje:

```http
POST /api/chat/query
Content-Type: application/json
```

```json
{
  "conversation_id": 1,
  "message": "Cuales son los requisitos para regularizar una materia?"
}
```

3. Leer historial:

```http
GET /api/conversations/1
```

Los mensajes usan campos heredados del modelo inicial:

```text
rol_mensaje
contenido_texto
conversacion_id
```

## Supabase y modelo de datos

`tables.sql` contiene el modelo objetivo para Supabase/PostgreSQL con pgvector:

- `app_users`
- `categorias`
- `documentos`
- `documento_versiones`
- `document_chunks`
- `document_embeddings`
- `conversaciones`
- `mensajes`
- `audit_logs`
- `message_documents`
- `feedback`
- `audio_interactions`
- `pii_mappings`

Estado de uso actual:

- `/me` usa `UsersService` y `UsersRepository` contra `app_users`.
- `/ready` usa `SystemService` y `SystemRepository` para chequear `app_users`, bucket `documents` y tabla `document_embeddings`.
- Las demas rutas todavia no escriben en Supabase.

## Estructura

```text
app/
  api/
    admin/routes.py
    chat/routes.py
    conversations/routes.py
    router.py
  core/
    config.py
    logging.py
    security.py
    supabase.py
  repositories/
    system_repository.py
    users_repository.py
  schemas/
    admin.py
    chat.py
    common.py
    system.py
  services/
    system_service.py
    users_service.py
  utils/
    files.py
```

Documentos relevantes:

```text
AGENTS.md
FRONTEND_API_INTEGRATION.md
modelo_inicial_datos.md
requisitos.md
tables.sql
```

## Persistencia y storage

Actual:

- Los documentos y audios subidos se escriben en `storage/`.
- Los metadatos de documentos/audios siguen en memoria.
- Ocultar una conversacion no la borra fisicamente del store.

Objetivo:

- Persistencia real en Supabase/PostgreSQL.
- Versionado documental real.
- Trazabilidad RAG por documento/chunk usado.
- Auditoria persistente por respuesta generada.
- Storage privado para documentos y audios.

## Prioridades tecnicas

1. Persistencia real de historial, documentos, auditoria, feedback y audio metadata.
2. Gestion documental con versionado real en Supabase Storage.
3. Pipeline RAG real con extraccion, chunking, embeddings y recuperacion.
4. Integracion real con OpenRouter u otro proveedor IA configurable.
5. STT/TTS real para consultas por voz.
6. Workers asincronos para tareas pesadas.
7. Tests automatizados, observabilidad y metricas reales.

## Advertencias de desarrollo

- No reemplazar `create_app()` por una instancia plana de `FastAPI()`.
- No agregar una base de datos nueva ni librerias grandes sin implementar realmente la capacidad asociada.
- No romper el aislamiento por `external_auth_id`.
- No convertir ocultamiento de conversaciones en borrado fisico.
- No asumir que `/ready` valida OpenAI real; actualmente solo verifica presencia de key.
- No asumir que los paths de audio/documentos son URLs publicas.
- Mantener separado el codigo de RAG, voz, IA, historial y documentos.
