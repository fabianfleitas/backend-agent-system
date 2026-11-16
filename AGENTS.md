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
- **Auth:** implementado con JWT de Supabase Auth; `get_auth_context()` valida JWT de Supabase (`external_auth_id` = `auth.users.id`), luego `is_active` en `app_users`, luego `institucion_miembros` (`tipo_miembro`, `institucion_id`) y `platform_admins` (`is_platform_admin`); `app_users.role` deprecado; headers delegados (`X-*`) obsoletos; cliente debe enviar `Authorization: Bearer <jwt>`.
- **Persistencia parcial real:** `/me` usa Supabase mediante `UsersService` y `UsersRepository`; tras transición, `get_auth_context()` valida JWT de Supabase (`external_auth_id` = `auth.users.id`) y resuelve membresía institucional.
- **Protección de cruzado:** acceso a recurso de otra institución devuelve 404; `app_users.role` no determina acceso institucional.
- **Readiness parcial real:** `/ready` consulta Supabase mediante `SystemService` y `SystemRepository`
- **Persistencia real:** conversaciones, mensajes, documentos, versiones, audio metadata, auditoria, `message_documents` y feedback persisten en Supabase mediante repositories
- **Storage real (Supabase Storage):** archivos subidos guardados en `SUPABASE_STORAGE_BUCKET_DOCUMENTS` y `SUPABASE_STORAGE_BUCKET_AUDIO` con prefijo institucional (`{institucion_id}/documents/`, `{institucion_id}/audio/`), no solo `storage/` local. Metadatos y trazabilidad en Supabase.
- **Billing / Stripe:** endpoints administrativos (`/api/admin/stripe/*`) y webhook (`/api/billing/stripe/webhook`) implementados con integración real a Stripe; persistencia real en Supabase (`suscripciones`, `pagos`, `comprobantes`, `stripe_eventos`); `subscription_data` con metadata institucional; alignment de checks DB (`003_billing_estado_checks.sql`).
- **Gestión documental:** carga de PDFs, versionado, descarga del PDF original y reindexacion con extraccion/indexacion local o embeddings reales segun `EMBEDDINGS_ENABLED`; categorías con precedencia global/institucional (`categorias.institucion_id` NULL = global; merge para admin institucional, precedencia institucional por nombre case-insensitive; platform admin gestiona solo globales); validación de categoría al crear documento.
- **FASE A-H implementadas:** B (Auth Supabase + RBAC), A (aislamiento multi-institución), D (RAG aislado por institución), E (conversaciones/voz), C (documental con categorías), F (audit/PII) implementada (ver PII/anonimización más abajo), G (billing/Stripe: checkout, suscripción, webhook, persistencia real) completada; H (dashboard) productiva: el Admin Dashboard SPA opera sobre el contrato real; además de los agregados institucionales (`/api/admin/conversations`, 2026-09-20), sin marcado de fase.
- **Modelo SQL objetivo:** `migrations/001_multi_institution.sql`; esquema completo en `all_tables.json`; `tables.sql` (esquema de referencia en la raíz).
- **RAG parcial real:** recuperacion de contexto real en `chat/query` (retrieval de chunks + trazabilidad en `message_documents`); embeddings mediante `OpenAIEmbeddingsClient` y OpenAI directo; generacion/juez via OpenRouter cuando están habilitados; `chat/voice` transcribe con STT OpenRouter y alimenta esa transcripcion al pipeline RAG+LLM (tag `[voice]` en audit); sintetiza respuesta via TTS OpenRouter con degradacion graceful si falla. El upstream de OpenRouter depende del modelo/ruta configurados y no se asume que cambie automáticamente.
- **Gestion documental real parcial:** carga de PDFs, versionado y reindexacion con extraccion/indexacion local o embeddings reales segun `EMBEDDINGS_ENABLED`
- **Procesamiento asincrono:** no implementado; `Celery`/`Redis` aun no existen en el codigo (**fuera de alcance MVP**, decision 2026-09-20m; indexacion/reindex y scripts manuales cubren el flujo)
- **Testing:** existe `tests/` con cobertura en desarrollo para servicios e integraciones criticas

## Arquitectura objetivo

Segun `migrations/001_multi_institution.sql` y `all_tables.json`, el sistema debe evolucionar hacia:

- **RAG desde el inicio:** indexacion documental, embeddings, recuperacion de contexto y prompts contextualizados
- **Persistencia real:** historial permanente, audios, documentos, auditoria, feedback y embeddings
- **Voz real:** almacenamiento de audio, transcripcion STT y respuesta sintetizada TTS
- **Gestion documental:** carga de PDFs, versionado, documento activo y reindexacion
- **IA externa:** integracion con OpenRouter con capacidad de cambiar modelo/proveedor
- **Procesamiento asincrono:** tareas pesadas desacopladas para indexacion, embeddings y voz (**fuera de alcance MVP**, decision 2026-09-20m)
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

Estado objetivo: autenticación con JWT de Supabase Auth.

- `get_auth_context()` resuelve `external_auth_id` desde `auth.users.id` (campo `sub` del JWT de Supabase), luego valida `is_active` en `app_users`, luego resuelve membresía activa en `institucion_miembros` (`tipo_miembro`, `institucion_id`) y `platform_admins` (`is_platform_admin`).
- `app_users.role` está deprecado como fuente de autorización; no se consulta para permisos institucionales.
- Headers delegados (`X-External-Auth-Id`, `X-User-Type`, etc.) quedan obsoletos; el cliente debe enviar `Authorization: Bearer <jwt>`.
- Separación clara:
  - `institucion_miembros` → administración de la institución (`/api/admin/*`)
  - `platform_admins` → administración global (`/api/platform/*`) implementada; guard `get_platform_admin_auth()`/`require_platform_admin()`; sin bypass
- Regla de acceso cruzado: 404 si el recurso no pertenece a `auth.institucion_id`; el único bypass es `is_platform_admin` para `/platform/*`.

### Deprecación de `app_users.role` (política)

- **Estado:** `app_users.role` está **deprecado**. NO es fuente de autorización (ni institucional ni de plataforma).
- **Reemplazo:** `institucion_miembros.tipo_miembro` (`ADMIN | SECRETARIA | ESTUDIANTE`) para permisos institucionales; `platform_admins.is_platform_admin` para permisos de plataforma.
- **En código:** se sigue escribiendo `role='STUDENT'` al crear un usuario (`users_repository.create_user`, `security.py`) solo por compatibilidad de esquema; no se lee para decidir accesos.
- **En API:** `UserOut.role` se expone mapeado (`_role_out`) por compatibilidad con el frontend; no debe usarse para ocultar/mostrar capacidades.
- **Timeline:** se eliminará de `UserOut`/OpenAPI en una versión futura; no crear dependencias nuevas sobre él.

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
PUT /me
```

Rutas expuestas bajo `/api`:

```text
POST   /api/public/solicitudes-acceso
POST   /api/conversations/
GET    /api/conversations/
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
GET    /api/admin/documents/{documento_id}/download
POST   /api/admin/documents/{documento_id}/versions
DELETE /api/admin/documents/{documento_id}
POST   /api/admin/reindex
GET    /api/admin/audit
GET    /api/admin/audit/export
GET    /api/admin/users
GET    /api/admin/feedback
DELETE /api/admin/feedback/{feedback_id}
GET    /api/admin/metrics
GET    /api/admin/metrics/export
GET    /api/admin/conversations
GET    /api/admin/escalamientos
POST   /api/admin/escalamientos/{notification_id}/resolve

GET    /api/admin/categories
POST   /api/admin/categories
PUT    /api/admin/categories/{categoria_id}
DELETE /api/admin/categories/{categoria_id}

GET    /api/admin/config
PUT    /api/admin/config/{clave}
GET    /api/admin/smtp
PUT    /api/admin/smtp
GET    /api/admin/notifications
POST   /api/admin/notifications/send-test
GET    /api/admin/email-templates
POST   /api/admin/email-templates
PUT    /api/admin/email-templates/{template_id}
DELETE /api/admin/email-templates/{template_id}

GET    /api/admin/subscription
GET    /api/admin/subscription/history
GET    /api/admin/plan
GET    /api/admin/plans
GET    /api/admin/pagos
GET    /api/admin/comprobantes
GET    /api/admin/comprobantes/export
POST   /api/admin/stripe/checkout
POST   /api/admin/stripe/portal-session
POST   /api/admin/stripe/create-subscription
POST   /api/admin/stripe/cancel-subscription
POST   /api/admin/stripe/reactivate-subscription
POST   /api/admin/stripe/change-plan
POST   /api/admin/stripe/sync-plan
GET    /api/admin/stripe/subscription

POST   /api/billing/stripe/webhook

GET    /api/platform/institutions
GET    /api/platform/institutions/{institucion_id}
POST   /api/platform/institutions
PUT    /api/platform/institutions/{institucion_id}
DELETE /api/platform/institutions/{institucion_id}
GET    /api/platform/institutions/{institucion_id}/members
POST   /api/platform/institutions/{institucion_id}/members
DELETE /api/platform/institutions/{institucion_id}/members/{member_id}
GET    /api/platform/users
POST   /api/platform/users
DELETE /api/platform/users/{external_auth_id}
GET    /api/platform/admins
POST   /api/platform/admins
DELETE /api/platform/admins/{external_auth_id}
GET    /api/platform/metrics
GET    /api/platform/metrics/export
GET    /api/platform/audit
GET    /api/platform/audit/export
GET    /api/platform/plans
POST   /api/platform/plans
PUT    /api/platform/plans/{plan_id}
DELETE /api/platform/plans/{plan_id}
GET    /api/platform/subscriptions
GET    /api/platform/pagos
GET    /api/platform/comprobantes
GET    /api/platform/comprobantes/export
```

Notas:

- La ruta de salud actual es `/health`, no `/api/health`.
- **Endpoint público:** `POST /api/public/solicitudes-acceso` es el único endpoint de negocio sin `Authorization` (formulario público `/solicitar-acceso` del dashboard). Valida consentimiento y correo, usa honeypot (`empresa`) y persiste en `solicitudes_acceso` (estado `PENDIENTE`); avisa por correo a `SOLICITUDES_EMAIL` si está configurado, con fallo suave (la persistencia no depende del envío). Rate limit propio (`/api/public/solicitudes-acceso:5:60`). El esquema global de OpenAPI fija `security: [{bearerAuth: []}]`, por eso la ruta lo sobrescribe con `openapi_extra={"security": []}` al no usar dependencia de auth.
- Las rutas antiguas `/api/student/*` ya no son el contrato actual.
- `chat/query` recupera contexto real via RAG (`sources`, `message_documents`, `embedding_model` en audit) cuando `EMBEDDINGS_ENABLED=true` y hay versiones `READY`; cuando `LLM_ENABLED=true` la respuesta es generada por OpenRouter sobre el contexto (fallback controlado si el LLM falla, con sources reales y error en `observaciones`); con `LLM_ENABLED=false` la respuesta text es mock. Con `LLM_HISTORY_ENABLED=true` (default) el prompt incluye los turnos previos de la conversacion (aislados por conversacion/usuario, recortados por token budget), pero el contexto RAG sigue siendo la fuente de verdad. Con `JUDGE_ENABLED=true` (o `config_parametros.judge_enabled`, precedencia institucional > global) cada respuesta generada por el LLM es evaluada con LLM-as-a-Judge (`JudgeService`, `score_fidelidad/relevancia/contexto` 0-1 en `audit_logs`, nota `JUDGE:ok|JUDGE_FAILED`); con `false` no hay llamada extra. El muestreo se controla con `judge_sample_rate` (`config_parametros`, 0.0 interactivo / 1.0 evaluación); si la consulta no cae en la muestra, se registra `JUDGE:skipped_sample`. Los modelos se resuelven por institución: `llm_model` para generación y `judge_model` para el juez (`config_parametros`, precedencia institucional > global > `settings`/.env); el admin institucional puede crear su propio override desde `PUT /api/admin/config/{clave}`. `llm_max_tokens`, temperatura e historial siguen siendo globales.
- `POST /api/chat/regenerate` (S11): regenera la última respuesta del asistente **reemplazándola in-place** (no agrega turno); re-ejecuta RAG+LLM+judge, crea un nuevo `audit_log` y actualiza `message_documents`. Requiere un turno previo (404 si no existe).
- `chat/voice` transcribe real el audio via STT cuando `STT_ENABLED=true` (cliente compatible OpenAI apuntando a `OPENROUTER_BASE_URL` con `OPENROUTER_API_KEY`; endpoint `POST /audio/transcriptions`; modelo default `stt_model=x-ai/grok-stt-1.0`, `stt_response_format=verbose_json` configurable). Si `STT_ENABLED=false` la transcripcion es mock. Con `STT_ENABLED=true` la transcripcion se alimenta al mismo pipeline RAG+OpenRouter de `chat/query` (respuesta real, guard de dominio o fallback; tag `[voice]` en `observaciones`); con `STT_ENABLED=false` la respuesta queda mock. Con `TTS_ENABLED=true` la respuesta se sintetiza a audio via `/audio/speech` de OpenRouter (modelo `tts_model` default `hexgrad/kokoro-82m`, voz `tts_voice` default `ef_dora`, formato `tts_response_format`) guardado en `ruta_audio_respuesta`; si TTS falla, degradacion graceful con nota `TTS_FAILED` en `observaciones`.
- `admin/documents` persiste archivos en disco y metadatos en Supabase; si `EMBEDDINGS_ENABLED=false` extrae texto localmente y si esta activo indexa chunks y embeddings.
- `admin/reindex` reindexa versiones activas con `IndexingService`; no es solo un cambio de estado mock.
- `GET /api/admin/config`, `PUT /api/admin/config/{clave}` (configuración operativa institucional + global; `editable_desde_dashboard`; precedencia institucional > global)
- `GET /api/admin/subscription`, `GET /api/admin/plan`, `GET /api/admin/pagos`, `GET /api/admin/comprobantes` (billing lectura, aislamiento por institución)
- `GET /api/platform/institutions`, `GET /api/platform/institutions/{id}`, `GET/POST /api/platform/institutions/{id}/members`, `DELETE /api/platform/institutions/{id}/members/{member_id}`, `GET /api/platform/users`, `GET /api/platform/metrics`, `GET /api/platform/audit`, `GET /api/platform/plans`, `GET /api/platform/subscriptions`, `GET /api/platform/pagos`, `GET /api/platform/comprobantes` (administración global con `require_platform_admin()`)
- `POST/PUT/DELETE /api/platform/institutions[/{id}]` y `POST/PUT/DELETE /api/platform/plans[/{id}]` (CRUD platform admin; delete = soft-deactivate `activo=false`; planes sincronizados con Stripe vía `sync-plan`)
- **Gestión de usuarios y platform admins (`/api/platform`):** `POST /api/platform/users` crea `app_users` (409 si ya existe) con membresía institucional opcional en un solo call (`institucion_id`/`tipo_miembro`); `DELETE /api/platform/users/{external_auth_id}` = desactivación en cascada (soft): `app_users.is_active=false` + membresía activa + `platform_admins`. `GET/POST /api/platform/admins` lista y concede admins de plataforma (upsert soft en `platform_admins`); `DELETE /api/platform/admins/{external_auth_id}` revoca (soft, `is_active=false`). Todos protegidos con `get_platform_admin_auth()`. *Decisión a revisar en el futuro: la creación de usuario incluye la membresía en el mismo call.*
- **Moderación de feedback:** `DELETE /api/admin/feedback/{feedback_id}` oculta (soft) un feedback de la institución del admin (`feedback.is_active=false`, no borrado físico; 404 si no existe o no pertenece a la institución). El listado `GET /api/admin/feedback` excluye inactivos salvo `include_inactive=true` (repo). Migración `migrations/008_feedback_is_active.sql`.
- `admin/users` lista usuarios de Supabase mediante `UsersRepository` (ahora con `institucion_id`, `tipo_miembro`, `is_platform_admin`, `nombre_institucion`).
- `admin/metrics` expone metricas IA agregadas desde `audit_logs` y `message_documents` (outcomes LLM/GUARD/LLM_FAILED, rates, tokens por modelo, avg similarity de retrieval, split voice/text).
- **Granularidad ADMIN vs SECRETARIA (S8):** los endpoints reservados de `/api/admin/*` (billing/Stripe, `/config`, `/users`, `/feedback`) usan `get_institution_admin_only_auth` (`require_institution_admin_strict`: exige rol ADMIN). Los operativos (documentos, categorías, auditoría, métricas, conversaciones, escalamientos) siguen con `get_admin_auth` (ADMIN|SECRETARIA).
- **Auditoría de acciones de gestión (S9):** `AuditRepository.log_action(action, external_auth_id, institucion_id, detalle)` registra en `audit_logs` (con `conversacion_id`/`mensaje_id` NULL) las acciones de gestión: `DOC_UPLOAD/DOC_VERSION/DOC_DEACTIVATE/DOC_REINDEX` (documents_service), `CATEGORY_CREATE/UPDATE/DEACTIVATE` (categories_service), `FEEDBACK_HIDE` (admin_service), `PLATFORM_INSTITUTION_*`, `PLATFORM_MEMBER_*`, `PLATFORM_USER_*`, `PLATFORM_ADMIN_*`, `PLATFORM_PLAN_*` (platform routes), y `BILLING_*` (billing_service: CHECKOUT, CREATE_SUBSCRIPTION, CANCEL, REACTIVATE, CHANGE_PLAN, PORTAL; y BILLING_SYNC_PLAN en la ruta admin). El dashboard muestra "Gestión" cuando `mensaje_id` es NULL.
- **Evaluación (S12):** `eval/` incluye los harnesses de Gold Dataset, k6, WER y PII. El 2026-11-08 se ejecutó un A/B real con 25 preguntas emparejadas y Supabase local sintético: juez OFF P50 2.176 ms/P95 3.936 ms; juez ON P50 4.189 ms/P95 7.090 ms, fidelidad 0.996, relevancia 1.0, contexto 1.0. El WER de los 6 audios TTS existentes se completó tras cargar créditos: macro 1.52 % y corpus 1.75 %. La carga local mock cubrió 1/8/50/100 VUs y una corrida sostenida de 240 solicitudes; no demuestra producción. Sigue sin revisión humana ni encuesta de validación. Evidencia versionada: `docs/evidencias/2026-11-08/`; estado y protocolo: `docs/PLAN_VALIDACION_TECNICA.md` y `eval/README.md`.
- **Despliegue (S13):** `Dockerfile` (python:3.12-slim), `.dockerignore`, `docker-compose.yml` (backend + `admin-dashboard`), `.github/workflows/deploy.yml` (publica imagen en GHCR). Archivos en Supabase Storage (sin volumen persistente; el startup crea `storage/`). CORS por env (`CORS_ALLOW_ORIGINS`); rate limit en memoria es por proceso (con varios workers no es global).
- **Backups (S6):** `scripts/backup_db.py` hace `pg_dump` de `DATABASE_URL` a `BACKUP_DIR` (default `backups/`) con retención `BACKUP_RETENTION_DAYS` (default 7). Programar cron diario (ver `docs/BACKUP.md`). Alternativa: backups gestionados/PITR de Supabase.
- `admin/conversations` lista todas las conversaciones de la institución del admin (CU-22, agregado institucional) con paginación (`limit`/`offset`), filtro `include_hidden` y `message_count`/`external_auth_id` por conversación; protegido con `get_admin_auth` (aislamiento por `institucion_id`).
- **PII/anonimización:** con `PII_ANONYMIZATION_ENABLED=true` (o `config_parametros.pii_anonymization_enabled`, precedencia institucional > global), `chat/query` y `chat/voice` anonimizan la pregunta antes de retrieval/LLM (Presidio NER `pii_nlp_model` default `es_core_news_md` + formatos locales cédula/teléfono + self-PII del perfil; tokens `[PII_TIPO_N]`; mappings en `pii_mappings` con `audit_id` y `expires_at` TTL). La regla de falso positivo `Necesito` está acotada al span exacto y a entidades NER `LOCATION`/`PERSON` en español; no cambia el umbral global. Los formatos locales de cédula cubren tanto el patrón **uruguayo** (`X.XXX.XXX-X`) como el **paraguayo** (6–9 dígitos, con o sin puntos). El texto anonimizado llega al proveedor; el original queda en `contenido_anonimizado`/`pregunta_anonimizada` y en `pii_mappings`. Cuando la política está activa, la respuesta generada se **desanonimiza localmente** (`PiiService.restore`) antes de persistir el mensaje y el audit (nota `DEANON:<n>`; `respuesta_texto` queda restaurada, coherente con `pregunta_original`). Si el detector no esta disponible y la politica esta ON, el flujo falla cerrado (`LLM_UNAVAILABLE_MESSAGE`, observaciones `PII_UNAVAILABLE`, sin llamadas externas). Config: `PII_MAPPING_RETENTION_DAYS` (default 90), `PII_NLP_MODEL`, `PII_LANGUAGE`; purga TTL con `scripts/purge_pii_mappings.py`.
- **Derivación a operador humano (escalamiento):** con `HANDOFF_ENABLED=true` (o `config_parametros.handoff_enabled`), cuando la consulta queda fuera de dominio (guard), el LLM falla o se detecta frustración, el sistema crea un escalamiento reutilizando `notificaciones` (`tipo='SYSTEM'`, `canal='IN_APP'`, `destinatario='SECRETARIA'`, `clave_idempotencia='handoff:{audit_id}'`, workflow en `datos` jsonb: `escalamiento`, `motivo`, `resumen`, `conversacion_id`, `mensaje_id`, `audit_id`, `workflow_estado` PENDING/RESOLVED, `resolved_by`, `resolved_at`). Triggers configurables: `handoff_trigger_on_guard` (true), `handoff_trigger_on_llm_failure` (true), `handoff_frustration_enabled` (false, palabras clave). Nota en audit `HANDOFF:<motivo>`. Endpoints admin (staff): `GET /api/admin/escalamientos` (paginado, filtro `estado`) y `POST /api/admin/escalamientos/{notification_id}/resolve`. Migración `migrations/009_judge_handoff_config.sql` (parámetros globales, sin cambios de esquema).
- **Rate limiting:** token bucket in-memory (`app/core/rate_limit.py`, middleware en `main.py`), exentos `/health` `/ready` y el webhook de Stripe. Configurable vía `RATE_LIMIT_ENABLED`, `RATE_LIMIT_DEFAULT_LIMIT`, `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`, `RATE_LIMIT_RULES` (ver `.env.example`). **Nota:** el bucket es por proceso; con múltiples workers no es un límite global distribuido.
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

Usar `migrations/001_multi_institution.sql` y `all_tables.json` como guia funcional (documentos antiguos `requisitos.md`, `modelo_inicial_datos.md` archivados; `borrar/` no existe).

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

## Convenciones

- Preferir `from __future__ import annotations` en archivos Python nuevos o modificados.
- Modelos de dominio temporales actuales: `@dataclass`.
- Schemas de entrada/salida: `pydantic.BaseModel`.
- Para escritura de archivos usar `app/utils/files.py`.
- `safe_join()` ya NO existe; los paths se validan con `_validate_bucket_path` en `storage_repository.py` y se generan con `uuid4().hex`.
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
- `presidio-analyzer` (detección NER PII) — requiere modelo spaCy: `python -m spacy download es_core_news_md`

### Objetivo futuro

Agregar dependencias solo cuando se implemente realmente la capacidad asociada:

- Celery / Redis (**fuera de alcance MVP**, decision 2026-09-20m)
- observabilidad y metricas ampliadas
- otras librerias de embeddings (hoy `openai` cubre el modelo configurado)

## Prioridades de implementacion

Si vas a extender el sistema, prioriza en este orden:

1. Persistencia real de historial, documentos, auditoria, feedback y audio metadata
2. Gestion documental con versionado real y Supabase Storage
3. Pipeline RAG real con trazabilidad por documentos/chunks usados
4. Integracion real con OpenRouter
5. STT/TTS real para consultas de voz
6. Workers asincronos para tareas pesadas (**fuera de alcance MVP**, decision 2026-09-20m)
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
