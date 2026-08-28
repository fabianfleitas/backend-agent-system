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
- **Auth:** implementado con JWT de Supabase Auth (`PLAN_MULTI_INSTITUCION_DECISIONES.md`); `get_auth_context()` valida JWT de Supabase (`external_auth_id` = `auth.users.id`), luego `is_active` en `app_users`, luego `institucion_miembros` (`tipo_miembro`, `institucion_id`) y `platform_admins` (`is_platform_admin`); `app_users.role` deprecado; headers delegados (`X-*`) obsoletos; cliente debe enviar `Authorization: Bearer <jwt>`.
- **Persistencia parcial real:** `/me` usa Supabase mediante `UsersService` y `UsersRepository`; tras transición, `get_auth_context()` valida JWT de Supabase (`external_auth_id` = `auth.users.id`) y resuelve membresía institucional.
- **Protección de cruzado:** acceso a recurso de otra institución devuelve 404; `app_users.role` no determina acceso institucional.
- **Readiness parcial real:** `/ready` consulta Supabase mediante `SystemService` y `SystemRepository`
- **Persistencia real:** conversaciones, mensajes, documentos, versiones, audio metadata, auditoria, `message_documents` y feedback persisten en Supabase mediante repositories
- **Storage real (Supabase Storage):** archivos subidos guardados en `SUPABASE_STORAGE_BUCKET_DOCUMENTS` y `SUPABASE_STORAGE_BUCKET_AUDIO` con prefijo institucional (`{institucion_id}/documents/`, `{institucion_id}/audio/`), no solo `storage/` local. Metadatos y trazabilidad en Supabase.
- **Billing / Stripe:** endpoints administrativos (`/api/admin/stripe/*`) y webhook (`/api/billing/stripe/webhook`) implementados con integración real a Stripe; persistencia real en Supabase (`suscripciones`, `pagos`, `comprobantes`, `stripe_eventos`); `subscription_data` con metadata institucional; alignment de checks DB (`003_billing_estado_checks.sql`).
- **Gestión documental:** carga de PDFs, versionado y reindexacion con extraccion/indexacion local o embeddings reales segun `EMBEDDINGS_ENABLED`; categorías aisladas por institución (`categorias.institucion_id`); validación de categoría al crear documento.
- **FASE A-H implementadas:** B (Auth Supabase + RBAC), A (aislamiento multi-institución), D (RAG aislado por institución), E (conversaciones/voz), C (documental con categorías), F (audit/PII) parcial, G (billing/Stripe: checkout, suscripción, webhook, persistencia real) completada; H (dashboard) pendiente.
- **Modelo SQL objetivo:** `migrations/001_multi_institution.sql`; esquema completo en `all_tables.json` (no `tables.sql` que no existe).
- **RAG parcial real:** recuperacion de contexto real en `chat/query` (retrieval de chunks + trazabilidad en `message_documents`); generacion de respuesta real via OpenRouter cuando `LLM_ENABLED=true`; `chat/voice` transcribe real via STT cuando `STT_ENABLED=true` y alimenta esa transcripcion al mismo pipeline RAG+OpenRouter (tag `[voice]` en audit); sintetiza respuesta a audio real via TTS (`/audio/speech`, OpenRouter) cuando `TTS_ENABLED=true` con degradacion graceful si falla; si STT esta off, voz es mock
- **Gestion documental real parcial:** carga de PDFs, versionado y reindexacion con extraccion/indexacion local o embeddings reales segun `EMBEDDINGS_ENABLED`
- **Procesamiento asincrono:** no implementado; `Celery`/`Redis` aun no existen en el codigo
- **Testing:** existe `tests/` con cobertura en desarrollo para servicios e integraciones criticas

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

## Auth (plan multi-institución)

Estado objetivo: autenticación con JWT de Supabase Auth. Ver `PLAN_MULTI_INSTITUCION_DECISIONES.md`.

- `get_auth_context()` resuelve `external_auth_id` desde `auth.users.id` (campo `sub` del JWT de Supabase), luego valida `is_active` en `app_users`, luego resuelve membresía activa en `institucion_miembros` (`tipo_miembro`, `institucion_id`) y `platform_admins` (`is_platform_admin`).
- `app_users.role` está deprecado como fuente de autorización; no se consulta para permisos institucionales.
- Headers delegados (`X-External-Auth-Id`, `X-User-Type`, etc.) quedan obsoletos; el cliente debe enviar `Authorization: Bearer <jwt>`.
- Separación clara:
  - `institucion_miembros` → administración de la institución (`/api/admin/*`)
  - `platform_admins` → administración global (`/api/platform/*`) **pendiente FASE H**; actualmente bypass via `/admin/*` documentado
- Regla de acceso cruzado: 404 si el recurso no pertenece a `auth.institucion_id`; el único bypass es `is_platform_admin` para `/platform/*`.

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
GET    /api/chat/audio/{audio_interaction_id}
POST   /api/chat/feedback

POST   /api/admin/documents
GET    /api/admin/documents
GET    /api/admin/documents/{documento_id}
POST   /api/admin/documents/{documento_id}/versions
DELETE /api/admin/documents/{documento_id}
POST   /api/admin/reindex
GET    /api/admin/audit
GET    /api/admin/users
GET    /api/admin/metrics
GET    /api/admin/categories
```

Notas:

- La ruta de salud actual es `/health`, no `/api/health`.
- Las rutas antiguas `/api/student/*` ya no son el contrato actual.
- `chat/query` recupera contexto real via RAG (`sources`, `message_documents`, `embedding_model` en audit) cuando `EMBEDDINGS_ENABLED=true` y hay versiones `READY`; cuando `LLM_ENABLED=true` la respuesta es generada por OpenRouter sobre el contexto (fallback controlado si el LLM falla, con sources reales y error en `observaciones`); con `LLM_ENABLED=false` la respuesta text es mock. Con `LLM_HISTORY_ENABLED=true` (default) el prompt incluye los turnos previos de la conversacion (aislados por conversacion/usuario, recortados por token budget), pero el contexto RAG sigue siendo la fuente de verdad.
- `chat/query` recupera contexto real via RAG (`sources`, `message_documents`, `embedding_model` en audit) cuando `EMBEDDINGS_ENABLED=true` y hay versiones `READY`; cuando `LLM_ENABLED=true` la respuesta es generada por OpenRouter sobre el contexto (fallback controlado si el LLM falla, con sources reales y error en `observaciones`); con `LLM_ENABLED=false` la respuesta text es mock. Con `LLM_HISTORY_ENABLED=true` (default) el prompt incluye los turnos previos de la conversacion (aislados por conversacion/usuario, recortados por token budget), pero el contexto RAG sigue siendo la fuente de verdad.
- `chat/voice` transcribe real el audio via STT cuando `STT_ENABLED=true` (cliente compatible OpenAI apuntando a `OPENROUTER_BASE_URL` con `OPENROUTER_API_KEY`; endpoint `POST /audio/transcriptions`; modelo default `stt_model=x-ai/grok-stt-1.0`, `stt_response_format=verbose_json` configurable). Si `STT_ENABLED=false` la transcripcion es mock. Con `STT_ENABLED=true` la transcripcion se alimenta al mismo pipeline RAG+OpenRouter de `chat/query` (respuesta real, guard de dominio o fallback; tag `[voice]` en `observaciones`); con `STT_ENABLED=false` la respuesta queda mock. Con `TTS_ENABLED=true` la respuesta se sintetiza a audio via `/audio/speech` de OpenRouter (modelo `tts_model` default `hexgrad/kokoro-82m`, voz `tts_voice` default `ef_dora`, formato `tts_response_format`) guardado en `ruta_audio_respuesta`; si TTS falla, degradacion graceful con nota `TTS_FAILED` en `observaciones`.
- `admin/documents` persiste archivos en disco y metadatos en Supabase; si `EMBEDDINGS_ENABLED=false` extrae texto localmente y si esta activo indexa chunks y embeddings.
- `admin/reindex` reindexa versiones activas con `IndexingService`; no es solo un cambio de estado mock.
- `GET /admin/config`, `PUT /admin/config/{clave}` (configuración operativa institucional + global; `editable_desde_dashboard`; precedencia institucional > global)
- `GET /admin/subscription`, `GET /admin/plan`, `GET /admin/pagos`, `GET /admin/comprobantes` (billing lectura, aislamiento por institución)
- `GET /platform/institutions`, `POST /platform/institutions/{id}/members`, `DELETE /platform/institutions/{id}/members/{member_id}`, `GET /platform/users`, `GET /platform/metrics`, `GET /platform/audit`, `GET /platform/plans`, `GET /platform/subscriptions`, `GET /platform/pagos`, `GET /platform/comprobantes` (administración global)
- `admin/users` lista usuarios de Supabase mediante `UsersRepository` (ahora con `institucion_id`, `tipo_membro`, `is_platform_admin`, `nombre_institucion`).
- `admin/metrics` expone metricas IA agregadas desde `audit_logs` y `message_documents` (outcomes LLM/GUARD/LLM_FAILED, rates, tokens por modelo, avg similarity de retrieval, split voice/text).
- El contrato para frontend esta documentado en `FRONTEND_API_INTEGRATION.md`.

## Persistencia actual vs objetivo

### Actual

- `/me` lee/crea usuario en Supabase si esta configurado.
- `/ready` verifica parcialmente Supabase, storage y tabla de embeddings.
- Conversaciones, mensajes, audio metadata, documentos, versiones, feedback, auditoria y trazabilidad RAG viven en Supabase.
- Si el proceso reinicia, se conserva el historial persistido; no depende de un `store` en memoria para el dominio principal.
- Los archivos subidos se guardan en `storage/`; los metadatos y trazabilidad se escriben en Supabase.

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

Usar `migrations/001_multi_institution.sql` y `all_tables.json` como guia funcional (documentos antiguos `requisitos.md`, `modelo_inicial_datos.md` movidos a `borrar/`).

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
- `openai` (embeddings, STT, TTS y cliente OpenRouter)

### Objetivo futuro

Agregar dependencias solo cuando se implemente realmente la capacidad asociada:

- Celery / Redis
- observabilidad y metricas ampliadas
- otras librerias de embeddings (hoy `openai` cubre el modelo configurado)

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
