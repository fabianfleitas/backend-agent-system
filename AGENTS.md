# AGENTS.md

## Proposito

Este repositorio implementa el backend de un asistente academico institucional.
El objetivo no es solo exponer APIs REST, sino evolucionar hacia una arquitectura
modular con RAG, voz, historial permanente, auditoria, versionado documental e
integracion con proveedores externos de IA.

Al trabajar en este proyecto, distinguir siempre entre:

- **estado actual implementado**
- **arquitectura objetivo requerida**

No asumir que los mocks actuales satisfacen los requisitos funcionales.

## Estado actual implementado

- **Framework:** FastAPI (Python 3.10+)
- **Entrypoint:** `app/main.py:create_app()`
- **Configuracion:** `pydantic-settings`, lee `.env` desde la raiz del proyecto
- **Auth:** delegada por headers en `app/core/security.py`
- **Persistencia parcial real:** `/me` usa Supabase mediante `UsersService` y `UsersRepository`
- **Readiness parcial real:** `/ready` consulta Supabase mediante `SystemService` y `SystemRepository`
- **Persistencia temporal:** conversaciones, mensajes, documentos, versiones, audio metadata, auditoria y feedback viven en `app/services/mock_store.py`
- **Storage local:** archivos subidos se guardan en `storage/`, `storage/audio/` y `storage/documents/`
- **Modelo SQL objetivo:** `tables.sql`
- **RAG / IA / STT / TTS:** no implementados realmente; las rutas de chat y voz usan respuestas mock
- **Procesamiento asincrono:** no implementado; `Celery`/`Redis` aun no existen en el codigo
- **Testing:** no existe directorio `tests/`

## Arquitectura objetivo

Segun `requisitos.md`, `modelo_inicial_datos.md` y `tables.sql`, el sistema debe evolucionar hacia:

- **RAG desde el inicio:** indexacion documental, embeddings, recuperacion de contexto y prompts contextualizados
- **Persistencia real:** historial permanente, audios, documentos, auditoria, feedback y embeddings
- **Voz real:** almacenamiento de audio, transcripcion STT y respuesta sintetizada TTS
- **Gestion documental:** carga de PDFs, versionado, documento activo y reindexacion
- **IA externa:** integracion con OpenRouter con capacidad de cambiar modelo/proveedor
- **Procesamiento asincrono:** tareas pesadas desacopladas para indexacion, embeddings y voz
- **Preparacion futura:** evolucion a tiempo real mediante WebSockets/WebRTC

## Invariantes funcionales

Estas reglas deben preservarse aunque la implementacion actual sea parcial:

- Responder solo con informacion institucional y reglamentos academicos
- No responder fuera del dominio academico institucional
- Mantener aislamiento por estudiante; no permitir acceso cruzado entre usuarios
- Conservar historial permanente; ocultar conversaciones no debe borrar registros fisicamente
- Proteger endpoints administrativos con autenticacion delegada y validacion de rol
- Mantener trazabilidad y auditoria de respuestas generadas por IA
- Mantener modulos desacoplados: RAG, voz, IA, historial, usuarios y documentos

## Entrypoint

`app/main.py:create_app()` es el factory principal; no reemplazarlo por una instancia plana de `FastAPI()`.

Run:

```bash
uvicorn app.main:app --reload
```

## Auth delegada

No usar JWT propio mientras no sea un requerimiento explicito.

Todos los endpoints de negocio dependen de headers delegados:

- `X-External-Auth-Id` es obligatorio
- `X-Auth-Provider` es opcional; por defecto `delegated`
- `X-User-Type` permite `ESTUDIANTE`, `ADMIN`, `SECRETARIA`
- `X-User-Email` es opcional

La extraccion del contexto se hace en `app/core/security.py:get_auth_context()`.
Los endpoints administrativos deben pasar por `require_admin()`.

Mapeo de roles:

- Header `ESTUDIANTE` -> respuesta `STUDENT`
- Header `SECRETARIA` -> respuesta `STAFF`
- Header `ADMIN` -> respuesta `ADMIN`

## Supabase

Configuracion:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`
- `SUPABASE_STORAGE_BUCKET_DOCUMENTS`, default `documents`
- `SUPABASE_STORAGE_BUCKET_AUDIO`, default `audio`

Reglas:

- `app/core/supabase.py:get_supabase_client()` debe seguir siendo el punto central para crear el cliente.
- No instanciar clientes Supabase sueltos en rutas.
- Usar repositories para acceso a Supabase y services para orquestacion.
- Si Supabase no esta configurado, `/ready` devuelve `not_ready`.
- Si Supabase no esta configurado, `/me` puede devolver `503`.
- No asumir que Supabase ya persiste todo el dominio; hoy solo cubre usuario actual y checks de readiness.

## API actual

Rutas globales:

```text
GET /health
GET /ready
GET /me
```

Rutas expuestas bajo `/api`:

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

Notas:

- La ruta de salud actual es `/health`, no `/api/health`.
- Las rutas antiguas `/api/student/*` ya no son el contrato actual.
- `chat/query` y `chat/voice` aun responden con contenido mock.
- `chat/voice` guarda el audio original localmente y crea un archivo de respuesta vacio; TTS real no existe todavia.
- `admin/documents` persiste archivos en disco, pero los metadatos siguen en memoria.
- `admin/reindex` solo cambia estado mock; no genera embeddings reales.
- `admin/users` lista usuarios del `mock_store`, no Supabase, en el estado actual del codigo.
- El contrato para frontend esta documentado en `FRONTEND_API_INTEGRATION.md`.

## Persistencia actual vs objetivo

### Actual

- `/me` lee/crea usuario en Supabase si esta configurado.
- `/ready` verifica parcialmente Supabase, storage y tabla de embeddings.
- Conversaciones, mensajes, audio metadata, documentos, versiones, feedback y auditoria viven en memoria.
- Si el proceso reinicia, se pierde el estado del `store`.
- Los archivos subidos se guardan en `storage/`, pero sus metadatos no son persistentes reales.

### Objetivo

El modelo esperado incluye al menos estas entidades conceptuales:

- usuario
- conversacion
- mensaje
- audio_interaccion
- documento
- documento_version
- document_chunk
- embedding
- mensaje_documento
- feedback
- log_auditoria
- pii_mapping

Usar `modelo_inicial_datos.md` y `tables.sql` como guia funcional, no como reflejo exacto de todo lo ya implementado.

## Estructura relevante

- `app/main.py`: factory FastAPI, rutas globales y startup
- `app/api/router.py`: router principal `/api`
- `app/api/chat/routes.py`: endpoints de chat texto, voz y feedback
- `app/api/conversations/routes.py`: endpoints de conversaciones e historial
- `app/api/admin/routes.py`: endpoints administrativos
- `app/core/config.py`: settings
- `app/core/security.py`: auth delegada y control de roles
- `app/core/supabase.py`: cliente Supabase centralizado
- `app/repositories/users_repository.py`: acceso a `app_users`
- `app/repositories/system_repository.py`: checks de readiness
- `app/services/users_service.py`: caso de uso de usuario actual
- `app/services/system_service.py`: readiness de sistema
- `app/services/mock_store.py`: almacenamiento temporal en memoria
- `app/utils/files.py`: helpers seguros para escritura y rutas
- `FRONTEND_API_INTEGRATION.md`: guia para consumo desde frontend
- `tables.sql`: esquema objetivo Supabase/PostgreSQL/pgvector

## Convenciones

- Preferir `from __future__ import annotations` en archivos Python nuevos o modificados.
- Modelos de dominio temporales actuales: `@dataclass`.
- Schemas de entrada/salida: `pydantic.BaseModel`.
- Para escritura de archivos usar `app/utils/files.py`.
- Usar `safe_join()` para evitar path traversal.
- Ejecutar `ensure_dir()` antes de escribir en disco.
- El startup crea `storage/`, `storage/audio/` y `storage/documents/`.
- Mantener rutas delgadas; mover orquestacion a services y acceso externo a repositories.
- No mezclar codigo mock con integraciones reales sin marcar claramente la frontera.

## Dependencias

### Actuales

- `fastapi`
- `uvicorn[standard]`
- `python-multipart`
- `pydantic-settings`
- `supabase`

### Objetivo futuro

Agregar dependencias solo cuando se implemente realmente la capacidad asociada:

- vector store / embeddings
- OpenRouter u otros proveedores IA
- Whisper o STT/TTS equivalente
- Celery / Redis
- testing automatizado
- observabilidad y metricas

## Prioridades de implementacion

Si vas a extender el sistema, prioriza en este orden:

1. Persistencia real de historial, documentos, auditoria, feedback y audio metadata
2. Gestion documental con versionado real y Supabase Storage
3. Pipeline RAG real con trazabilidad por documentos/chunks usados
4. Integracion real con OpenRouter
5. STT/TTS real para consultas de voz
6. Workers asincronos para tareas pesadas
7. Observabilidad, metricas y pruebas automatizadas

## Notas para agentes

- No asumir que "funciona" porque exista un endpoint; varios flujos son mocks.
- No introducir una base de datos o librerias grandes sin actualizar dependencias y conectar la capacidad real.
- No romper el aislamiento por `external_auth_id`.
- No convertir el ocultamiento de historial en borrado fisico.
- No responder preguntas fuera del dominio institucional una vez se implemente el flujo IA real.
- No exponer archivos de storage como publicos sin requerimiento explicito.
- No tratar paths de `ruta_audio_original`, `ruta_audio_respuesta` o `ruta_archivo` como URLs descargables.
- Al actualizar contratos de API, mantener sincronizado `FRONTEND_API_INTEGRATION.md`.
