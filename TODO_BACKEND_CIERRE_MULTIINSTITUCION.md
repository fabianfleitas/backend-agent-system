# TODO Backend — Cierre de arquitectura multiinstitución

**Proyecto:** Sistema de atención por agentes de voz con arquitectura RAG y capa de privacidad  
**Fecha:** 2026-08-25

## Objetivo

Cerrar el backend antes de la productivización final del Admin Dashboard, contemplando:

- autenticación JWT
- multiinstitución
- aislamiento y RLS
- RAG
- anonimización PII
- configuración institucional
- Platform Admin
- billing/Stripe
- métricas
- OpenAPI
- tests y QA

---

# 1. Auth y autorización

- [x] Backend autenticado mediante JWT de Supabase.
- [x] `Authorization: Bearer <jwt>`.
- [x] No depender de headers `X-*` antiguos.
- [x] `institucion_miembros.tipo_miembro` como fuente principal de permisos institucionales.
- [x] `platform_admins.is_active` para permisos de plataforma.
- [x] `app_users.role` queda como legacy/compatibilidad.
- [x] Revisar que ningún endpoint nuevo use `app_users.role` como fuente autoritativa.
- [x] Documentar formalmente la deprecación de `app_users.role`. **IMPLEMENTADO** — sección "Deprecación de `app_users.role` (política)" en `AGENTS.md`.

### Regla de pertenencia

**Decisión:** un usuario no debe pertenecer a varias instituciones.

- [x] Verificar la regla en service/repository (add_member + get_active_membership)
- [x] Impedir nuevas membresías múltiples (DB partial index 004 + ValueError 409)
- [x] Definir tratamiento de datos históricos que la incumplan (migración 004 conserva más reciente; resto deaktivado)
- [x] Agregar test específico (tests/test_membresia_unica.py)

### Platform Admin

- [ ] Platform admin sin institución → solo `/platform/*`.
- [ ] Para `/admin/*` debe tener membresía institucional válida.
- [ ] Revisar todos los endpoints con estas reglas.
- [ ] Agregar tests.

---

# 2. Aislamiento multiinstitución

**Decisión:** repositories/services + RLS como defensa adicional. No agregar `institucion_id` redundante a tablas transitivas.

- [x] `documento_versiones` → `documentos`.
- [x] `document_chunks` → `documento_versiones` → `documentos`.
- [x] `document_embeddings` → `document_chunks` → `documento_versiones` → `documentos`.
- [x] `mensajes` → `conversaciones`.
- [x] `message_documents` → `mensajes` → `conversaciones`.
- [x] Revisar cada repository con criterio de tenant isolation. **IMPLEMENTADO** — repos filtran por `institucion_id`/`external_auth_id`: `DocumentsRepository`, `ConversationsRepository`, `MetricsRepository`, `AuditRepository`, `CategoriesRepository`, `BillingRepository`, `ConfigRepository`, `RetrievalRepository.match_chunks`, `AudioRepository.get_audio_interaction` (`retrieval_repository.py`, `audio_repository.py:45-52`). Excepción: `MessagesRepository.get_message` no es institution-aware por sí mismo, pero a nivel service `ChatService.create_feedback` valida ownership + institución de la conversación (`chat_service.py:407-415`).
- [x] Revisar `SELECT`.
- [x] Revisar `INSERT`.
- [x] Revisar `UPDATE`.
- [x] Revisar `DELETE`.
- [x] Verificar que ningún `get_by_id()` permita recuperar recursos de otra institución.

### Respuesta cross-tenant

**Decisión:** usar `404` cuando revelar la existencia del recurso pueda romper el aislamiento.

- [x] Documentos.
- [x] Versiones/chunks/embeddings.
- [x] Conversaciones/mensajes.
- [x] Usuarios.
- [x] Billing.
- [x] Tests de `404` cross-tenant (base: `test_cross_tenant_routes.py`, `test_cross_tenant_repos.py`, `test_cross_tenant_chat.py`, `test_isolation.py`; faltan casos de rutas: audit/config/categories/users/metrics/billing/audio/feedback). **IMPLEMENTADO** — `tests/test_cross_tenant_admin.py` cubre listas (200 vacías), recursos únicos (404), feedback POST (404) y controles positivos.

---

# 3. RLS

- [x] RLS habilitado en tablas principales.
- [x] Policies existentes.
- [x] Helper functions existentes.
- [x] `force_rls = false` documentado.
- [ ] Revisar policies actuales.
- [ ] Revisar `SECURITY DEFINER`.
- [ ] Revisar `search_path`.
- [ ] Confirmar que no existan policies excesivamente permisivas.
- [ ] Documentar que el backend usa `service_role` y que su aislamiento principal está en application layer.
- [ ] Mantener RLS como defensa para accesos que no utilicen `service_role`.

---

# 4. RAG / Knowledge Base

## Ingesta

- [x] Extracción de texto.
- [x] Chunking.
- [x] Embeddings.
- [x] Persistencia en `document_chunks`.
- [x] Persistencia en `document_embeddings`.
- [x] Reindexación funcional para documentos indexados.

## Multiinstitución

- [x] Confirmar que retrieval nunca mezcle instituciones. **IMPLEMENTADO** — `RetrievalService.retrieve` exige `institucion_id` y devuelve error si es `None` (`retrieval_service.py:80-92`); RPC `match_document_chunks` filtra por `institucion_id` + `status='READY'` + `es_version_activa=true` (`migrations/001_multi_institution.sql`).
- [x] Aplicar filtro institucional en retrieval.
- [x] Verificar `match_document_chunks()` y funciones equivalentes.
- [x] Probar documento A vs documento B. **IMPLEMENTADO** — `tests/test_retrieval_isolation.py`, `tests/test_retrieval_service.py`.
- [x] Probar usuario A intentando consultar conocimiento de B.

## Estados

Validar:

`PENDING → PROCESSING → READY`

y:

`PROCESSING → ERROR`

- [x] `READY` implica realmente chunks + embeddings.
- [x] Actualizar `total_chunks`.
- [x] Actualizar `total_embeddings`.
- [x] Registrar `embedding_model`.
- [x] Registrar `indexed_at`.
- [x] Registrar `error_message`.
- [x] No marcar `READY` solo cambiando el status. **IMPLEMENTADO** — `IndexingService` escribe `PROCESSING → READY/FAILED` con `total_chunks`, `total_embeddings`, `embedding_model`, `indexed_at`, `error_message` (`indexing_service.py:58-174`).

---

# 5. PII / Anonimización

- [x] Revisar pipeline `audio/text → detección PII → anonimización → RAG/LLM`. **IMPLEMENTADO** — `app/services/pii_service.py` (Presidio NER + formatos locales cédula/teléfono + self-PII perfil; tokens `[PII_TIPO_N]`; fail-closed si detector no disponible), `app/repositories/pii_repository.py` (`pii_mappings` con `expires_at`), integración en `chat/query` y `chat/voice` (política `pii_anonymization_enabled` por institución/global; retrieval y LLM reciben texto anonimizado; raw + anonimizado persistidos en `contenido_anonimizado`/`pregunta_anonimizada`; mappings con `audit_id`; tag `PII:{n}` en observaciones).
- [x] Revisar `pii_mappings`. **IMPLEMENTADO** — tabla real con `expires_at` (align DB); retención TTL `PII_MAPPING_RETENTION_DAYS` y `scripts/purge_pii_mappings.py` para purgar vencidos.
- [x] Evitar PII real en logs. **IMPLEMENTADO** — los logs del pipeline PII no emiten el contenido original; en fail-closed solo se registra el `conversation_id`.
- [x] Evitar PII innecesaria en auditoría. **IMPLEMENTADO** — la auditoría guarda `pregunta_original` y `pregunta_anonimizada`; con política activa el texto enviado al proveedor es la versión anonimizada y los valores originales quedan solo en `pii_mappings` con TTL.
- [x] Revisar persistencia de mensajes. **IMPLEMENTADO** — `mensajes.contenido_anonimizado` guarda la versión anonimizada junto al original.
- [x] Definir retención/borrado de mappings. **IMPLEMENTADO** — TTL por `expires_at` (`pii_mapping_retention_days`, default 90) + `scripts/purge_pii_mappings.py --dry-run/--days`.
- [x] Tests de anonimización. **IMPLEMENTADO** — `tests/test_pii_service.py` (tokenización, merge de solapes, fail-closed sin detector, persistencia TTL) y `tests/test_pii_pipeline.py` (retrieval/LLM reciben anonimizado, fail-closed sin llamadas externas, OFF passthrough).
- [x] Test que confirme que el LLM recibe texto anonimizado cuando corresponde. **IMPLEMENTADO** — `tests/test_pii_pipeline.py::test_pii_activado_envia_texto_anonimizado_a_llm_y_persiste`.

### Criterio de cierre

Debe poder demostrarse que la información identificable del usuario no se envía al proveedor LLM cuando la política de privacidad exige anonimización.

**Demostración:** con `PII_ANONYMIZATION_ENABLED=true` (o `config_parametros.pii_anonymization_enabled`), `chat/query` y `chat/voice` anonimizan antes de retrieval/LLM (los tests de pipeline lo verifican); si el detector (Presidio + modelo spaCy `es_core_news_md`) no está disponible, el flujo falla cerrado (`LLM_UNAVAILABLE_MESSAGE`, observaciones `PII_UNAVAILABLE`) y no se llama a proveedores externos. Los originales quedan en `pii_mappings` con vencimiento TTL y purga scripteable.

---

# 6. Chat, conversaciones y voz

### Mensajes

**Decisión:** validar en service cargando/validando primero la conversación.

- [x] Confirmar implementación.
- [x] Verificar ownership de conversación.
- [x] Verificar acceso a mensajes.
- [x] Verificar `message_documents` — trazabilidad RAG insertada por `ChatService._answer_query` (`chat_service.py:266-286`); fuente de métricas (`metrics_repository.py:60-90`).
- [x] Tests cross-tenant. **IMPLEMENTADO** — `tests/test_cross_tenant_chat.py`, `tests/test_feedback_route.py`.

### Voz

- [x] Revisar `POST /api/chat/voice`. **IMPLEMENTADO** — pipeline STT→PII→RAG→OpenRouter→TTS con tags `[voice]`/`PII:{n}`/`TTS_FAILED` y degradación mock controlada.
- [x] Confirmar STT.
- [x] Confirmar anonimización. **IMPLEMENTADO** — `chat/voice` alimenta la transcripción al mismo pipeline PII de `chat/query` (retrieval/LLM reciben texto anonimizado; tag `PII:{n}` / fail-closed `PII_UNAVAILABLE` en observaciones).
- [x] Confirmar persistencia de audio según política. **IMPLEMENTADO** — audio a Supabase Storage con prefijo institucional `{institucion_id}/audio/` (`SUPABASE_STORAGE_BUCKET_AUDIO`).
- [x] Confirmar TTS.
- [x] Confirmar `GET /api/chat/audio/{audio_interaction_id}`. **IMPLEMENTADO** — `app/api/chat/routes.py:196-227` devuelve binario con `Content-Disposition: inline`.
- [x] Revisar aislamiento de audio. **IMPLEMENTADO** — `AudioService.get_response_audio` (`audio_service.py:74-104`): otra institución → 404, mismo usuario OK, otro usuario → 403, `is_platform_admin` bypass. Tests: `tests/test_audio_service.py`, `tests/test_chat_voice_route.py`.

---

# 7. Auditoría

- [x] Endpoint de auditoría.
- [x] RLS de auditoría.
- [x] Confirmar institución correcta en cada evento.
- [x] Confirmar actor autenticado.
- [x] Evitar PII innecesaria.
- [x] Confirmar aislamiento institucional.
- [x] Revisar relación `message_documents` → auditoría.
- [x] Cross-tenant audit 404: cubierto por `tests/test_cross_tenant_routes.py` + repo isolation
- [x] Cross-tenant auth/roles/back: `tests/test_auth_context.py`, `test_permissions`

---

# 8. Usuarios y membresías

- [x] `GET /api/admin/users`.
- [x] Completar `full_name`. **IMPLEMENTADO** — `AdminService.list_users` (`admin_service.py:24-56`) + `UserOut` (`app/schemas/common.py:105-115`).
- [x] Completar `institucion_id`.
- [x] Completar `tipo_miembro`.
- [x] Completar `is_platform_admin`.
- [x] Incluir `nombre_institucion` si corresponde.
- [x] ADMIN solo ve usuarios de su institución. **IMPLEMENTADO** — `UsersRepository.list_users` filtra miembros activos de la institución del auth (`users_repository.py:102-119`).
- [x] Platform admin ve el alcance permitido.
- [x] Usuario sin membresía correctamente bloqueado.
- [x] Membresía inactiva correctamente bloqueada.
- [x] Impedir membresía simultánea en varias instituciones.

---

# 9. `config_parametros`

La tabla ya fue creada.

- [x] Tabla creada.
- [x] RLS definitivo.
- [ ] Repository.
- [ ] Service.
- [ ] GET por institución.
- [ ] UPDATE/PUT para parámetros editables.
- [ ] Separar parámetros globales de institucionales.
- [ ] Validar tipos: `float`, `int`, `bool`, `string`, `json`.
- [ ] Validar conversión de `valor`.
- [ ] Respetar `editable_desde_dashboard`.
- [ ] Ignorar `activo = false`.
- [ ] Definir precedencia: institucional > global/default.
- [ ] Impedir que una institución modifique parámetros globales.
- [ ] Auditar cambios.
- [ ] Documentar parámetros soportados.

---

# 10. Billing / Stripe

## Alcance inicial

Primero modelo + repositories + endpoints de lectura. La integración Stripe completa puede quedar como siguiente subfase si aún no están disponibles las credenciales/contratos necesarios.

## Tablas

- [x] `planes`
- [x] `suscripciones`
- [x] `suscripcion_historial`
- [x] `pagos`
- [x] `comprobantes`
- [x] `stripe_eventos`
- [x] Checkout Session (`stripe/checkout`)
- [x] Subscription read (`stripe/subscription`), create/cancel/reactivate/change-plan, portal, sync-plan
- [x] Webhook (`/api/billing/stripe/webhook`) con persistencia real (`pagos`, `comprobantes`, `suscripciones`)
- [x] Aligned DB checks (`003_billing_estado_checks.sql`)
- [ ] Persistencia completa del webhook verificada con checkout pagado (próximo paso opcional)
- [ ] `notificaciones`
- [ ] `configuracion_smtp`
- [ ] `plantillas_email`

## Backend

- [x] Repositories.
- [x] Services.
- [x] Endpoints de lectura.
- [x] Planes.
- [x] Suscripciones.
- [x] Estado de suscripción.
- [x] Pagos.
- [x] Comprobantes.
- [x] Portal de facturación.

## Stripe completo

- [x] Checkout Session.
- [x] Webhooks.
- [x] Validación de firma.
- [x] Idempotencia — vía `stripe_eventos` (`StripeWebhookService.register_event`, `stripe_webhook_service.py:18-39`).
- [ ] Reintentos.
- [x] Sincronización de estados — handlers de webhook + `sync-plan`.
- [x] Cancelación.
- [x] Cambio de plan.
- [x] Renovación — `invoice.payment_succeeded` actualiza pagos/comprobantes/suscripciones.
- [x] Vencimiento. **IMPLEMENTADO (script manual)** — `scripts/check_subscription_expiry.py` (marca `EXPIRED` + historial + notificación cuando `fecha_vencimiento < now`); sin scheduler (Celery/Redis).
- [x] Facturación/comprobantes.
- [x] Persistencia de eventos Stripe.

---

# 11. Notificaciones y correo

- [ ] Repository de notificaciones.
- [ ] Service.
- [ ] Templates.
- [ ] SMTP.
- [ ] Notificación de vencimiento.
- [ ] Notificación de cambio de plan.
- [ ] Notificación de pago.
- [ ] Manejo de errores de envío.
- [x] Auditoría de envíos.

---

# 12. Platform Admin

**IMPLEMENTADO** — no faltan `/api/platform/*`; 12 endpoints operativos con guard `require_platform_admin()`/`get_platform_admin_auth` (`app/api/platform/routes.py`, `app/core/security.py:147-157`).

- [x] Definir contrato.
- [x] Crear repositories/services.
- [x] Crear endpoints.
- [x] Aplicar `is_platform_admin`.
- [x] Gestión de instituciones — CRUD completo (2026-09-20): `POST/PUT/DELETE /api/platform/institutions[/{id}]` (delete = soft-deactivate `activo=false`). Tests: `tests/test_platform_crud.py`.
- [x] Gestión de planes — CRUD (2026-09-20): `POST/PUT/DELETE /api/platform/plans[/{id}]` (delete = soft-deactivate; `stripe_price_id` se sincroniza aparte con `sync-plan`). Tests: `tests/test_platform_crud.py`.
- [x] Consulta de suscripciones.
- [x] Consulta de pagos.
- [x] Métricas globales (agregados + filtros/series).
- [x] Auditoría (endpoints, RLS, aislamiento, trazabilidad RAG por mensaje_documento) global según alcance.
- [ ] Evitar que platform admin sin membresía obtenga automáticamente permisos de `/admin/*`.

---

# 13. Métricas

Actualmente existen agregados consumidos por el dashboard.

- [x] Métricas actuales.
- [x] Filtros por período.
- [x] Filtro por categoría.
- [x] Filtro por modelo.
- [x] Filtro por documento.
- [x] Series temporales.
- [x] Métricas RAG.
- [x] Métricas de voz.
- [x] Tokens/modelos. **IMPLEMENTADO** — `GET /api/admin/metrics` acepta `desde/hasta/categoria_id/modelo/documento_id` + `granularidad` (`day`) + `series`; `tokens_by_model`; `AdminService.get_metrics` + `_build_series` (`admin_service.py:78-279`); test `tests/test_bloque2_metrics.py`.
- [x] Métricas (agregados + filtros período/categoría/modelo/documento + series temporales) globales de platform admin.

---

# 14. Categorías

- [x] `GET /api/admin/categories`.
- [x] CRUD completo si se decide necesario. **IMPLEMENTADO** — `POST /api/admin/categories`, `PUT/DELETE /api/admin/categories/{categoria_id}` (`app/api/admin/categories_routes.py`; tests `test_categories.py`, `test_categories_crud.py`).
- [x] Aislamiento institucional. **IMPLEMENTADO** — `CategoriesService`/`CategoriesRepository.get_by_id` filtra por `institucion_id`; `get_by_id_any` solo platform admin (`categories_service.py:14-27`).
- [x] Categorías (`GET /admin/categories`; CRUD pospuesto) globales/default.
- [x] Categorías (`GET /admin/categories`; CRUD pospuesto) institucionales.
- [ ] Definir precedencia global/institucional.

---

# 15. OpenAPI

- [x] Generar OpenAPI oficial desde backend (`scripts/generate_openapi.py`).
- [x] Versionarlo (archivo versionado en git).
- [x] Integrarlo al CI (`generate_openapi.py --check` en `.github/workflows/ci.yml`; artifact del diff al fallar).
- [x] Actualizar `openapi.current.json`.
- [x] Documentar errores `401/403/404/409/422/500` (descripción en `custom_openapi`).
- [x] Documentar paginación.
- [x] Documentar filtros.
- [x] Documentar permisos.
- [x] Documentar `/platform/*`.
- [x] Documentar billing.

---

# 16. Tests backend

## Auth

- [ ] JWT válido.
- [ ] JWT inválido.
- [ ] Usuario inexistente.
- [ ] Usuario inactivo.
- [ ] Sin membresía.
- [ ] Membresía inactiva.
- [ ] ADMIN.
- [ ] SECRETARIA.
- [ ] ESTUDIANTE.
- [ ] Platform admin.

## Multiinstitución

- [ ] A no puede leer B.
- [ ] A no puede modificar B.
- [ ] A no puede eliminar B.
- [ ] A no puede acceder a chunks de B.
- [ ] A no puede acceder a embeddings de B.
- [ ] A no puede acceder a conversaciones de B.
- [ ] A no puede acceder a auditoría de B.
- [ ] A no puede acceder al billing de B.

## RAG/PII

- [ ] Retrieval restringido por institución.
- [ ] Contexto del LLM restringido.
- [x] PII anonimizada. **IMPLEMENTADO** — ver §5: anonimización antes de retrieval/LLM con política activa, fail-closed sin detector.
- [ ] Voice respeta aislamiento.

## Billing

- [ ] Suscripción.
- [ ] Pagos.
- [ ] Comprobantes.
- [ ] Webhooks idempotentes.
- [ ] Estados de suscripción.

---

# 17. QA manual final

### ADMIN institución A

- [ ] Login.
- [ ] `/me`.
- [ ] Dashboard.
- [ ] Documentos.
- [ ] RAG.
- [ ] Chat.
- [ ] Conversaciones.
- [x] Auditoría.
- [ ] Configuración.

### ADMIN institución B

- [ ] Repetir pruebas.
- [ ] Confirmar que no aparecen datos de A.

### Usuario sin membresía

- [ ] `/me`.
- [ ] Acceso denegado a `/admin/*`.

### Platform Admin

- [ ] `/platform/*`.
- [ ] Acceso global permitido.
- [ ] Sin membresía institucional no obtiene automáticamente permisos `/admin/*`.

---

# 18. Seguridad final

- [ ] Secrets únicamente en variables de entorno.
- [ ] Nunca exponer `service_role_key`.
- [ ] No registrar JWT.
- [x] No registrar PII. **IMPLEMENTADO** — ver §5: el pipeline PII no emite originales en logs.
- [ ] No registrar API keys.
- [ ] Validar uploads.
- [ ] Validar MIME type.
- [ ] Limitar tamaño de archivos.
- [ ] Validar PDFs.
- [ ] Evitar path traversal.
- [ ] Revisar Storage.
- [ ] Revisar acceso a audio.
- [ ] Revisar errores internos expuestos.
- [ ] Revisar CORS.
- [x] Revisar rate limiting. **IMPLEMENTADO (in-memory)** — `app/core/rate_limit.py` (token bucket por IP+prefijo, middleware, exentos `/health` `/ready` webhook). Variables en `.env.example`. **Límite:** el bucket es por proceso; con múltiples workers no es un límite global. Distribuido (Redis) pospuesto explícitamente.
- [ ] Revisar timeouts.
- [ ] Revisar retries.

---

# 19. Documentación

- [ ] README backend actualizado.
- [ ] Arquitectura multiinstitución.
- [ ] Autenticación.
- [x] RLS definitivo.
- [x] PII. **IMPLEMENTADO** — ver §5.
- [ ] RAG.
- [ ] Billing/Stripe.
- [ ] Roles/permisos.
- [x] OpenAPI (`custom_openapi`, `openapi.current.json`, docs, errores, paginación, filtros).
- [ ] Variables de entorno.
- [x] `CONTROL.md` eliminado; verificación RLS/DB completada (migración 005/006 + policies verificadas). Documentado en TODO.

---

# 20. Criterio de cierre

El backend queda **CERRADO PARA INTEGRACIÓN FINAL CON EL DASHBOARD** cuando:

- [ ] Auth JWT funciona.
- [ ] Multiinstitución está probado.
- [ ] Aislamiento cross-tenant probado.
- [ ] RAG aislado por institución.
- [x] PII anonimizada según política. **IMPLEMENTADO** — ver §5.
- [ ] Chat texto funciona.
- [ ] Chat voz funciona.
- [x] Auditoría funciona.
- [x] `config_parametros` funciona (tabla, repo, service, endpoints GET/PUT, precedencia, audit).
- [ ] Billing tiene contrato y endpoints definidos.
- [ ] Stripe está implementado o explícitamente pospuesto.
- [ ] Platform API implementada o explícitamente pospuesta.
- [x] OpenAPI (`custom_openapi`, `openapi.current.json`) es fuente de verdad.
- [ ] Tests críticos pasan.
- [ ] QA multiinstitución pasa.
- [ ] Seguridad revisada.
- [x] Documentación actualizada (README, AGENTS, FRONTEND_API_INTEGRATION, CONTROL, openapi.current.json; borrar/ archivado).

---

# 21. Orden recomendado

### BLOQUE A — Seguridad y arquitectura
1. [ ] Revisar auth/roles.
2. [ ] Cerrar regla de una institución por usuario.
3. [ ] Auditoría multi-tenant.
4. [ ] Revisión final RLS.
5. [ ] Tests cross-tenant.

### BLOQUE B — RAG + privacidad
6. [ ] Validar retrieval multiinstitución.
7. [ ] Validar estados de indexación.
8. [x] Cerrar PII/anonymización. **IMPLEMENTADO** — ver §5.
9. [x] Tests RAG + PII. **IMPLEMENTADO** — `tests/test_pii_service.py` y `tests/test_pii_pipeline.py`.

### BLOQUE C — Configuración
10. [ ] RLS de `config_parametros`.
11. [ ] Repository/service.
12. [ ] Endpoints.
13. [ ] Precedencia global/institucional.
14. [ ] Auditoría.

### BLOQUE D — Platform
15. [ ] Contrato `/api/platform/*`.
16. [ ] Repositories/services.
17. [ ] Endpoints.
18. [ ] Tests.

### BLOQUE E — Billing
19. [ ] Revisar tablas.
20. [ ] Repositories/services.
21. [ ] Endpoints de lectura.
22. [ ] Contratos del Dashboard.
23. [x] Stripe. **IMPLEMENTADO**
24. [x] Webhooks/idempotencia. **IMPLEMENTADO**
25. [ ] Facturación (comprobantes OK) / notificaciones y recordatorios (SMTP, pendiente §11).

### BLOQUE F — Métricas y contrato
26. [x] Métricas avanzadas. **IMPLEMENTADO**
27. [x] Filtros/series. **IMPLEMENTADO**
28. [x] OpenAPI oficial. **IMPLEMENTADO** — `openapi.current.json` (fuente de verdad, sincronizado con el Admin Dashboard) + `/docs`.
29. [x] CI para OpenAPI. **IMPLEMENTADO** — `generate_openapi.py --check` en CI + artifact del diff al fallar.

### BLOQUE G — Cierre
30. [ ] Tests completos.
31. [ ] QA multiinstitución.
32. [ ] Seguridad.
33. [ ] Documentación.
34. [ ] Actualizar estado del proyecto.
35. [ ] Handoff definitivo al Admin Dashboard.


---
## Estado 2026-08-29 (post DB alignment + verificación RLS)
- BLOQUE 1-4 + DB alignment completado (005/006). Auth JWT, aislamiento multiinstitución, RAG aislado, docs, config (`config_parametros` completo), platform (`institucion_miembros`/`platform_admins`), billing lectura (`suscripciones`, `pagos`, `comprobantes`, `stripe_eventos`), métricas y OpenAPI.
- **DB real alineado:** defaults de `comprobantes` (`PENDING`), `suscripciones` (`TRIAL`), `tipo_miembro` (`ESTUDIANTE` + CHECK corregido + backfill), índices (`suscripcion_historial`, `categorias global`), `pii_mappings.expires_at`, `notificaciones.datos`, `categorias.orden/fecha_baja`, overload RAG legacy eliminado (`match_document_chunks` aislado). `all_tables.json` actualizado (sin LIMIT 100).
- **RLS revisado (§3):** policies verificadas (`qual`/`with_check`); aislamiento por institución confirmado (joins a `institucion_id` o `external_auth_id`). Funciones helper (`is_global_admin`, `is_platform_admin`, `is_institution_admin`, `is_institution_member`, `get_my_institution_id`) presentes. No se detectaron policies excesivamente permisivas sin filtro de tenant.
- Pospuesto explícito: PII/anónimo completo (§5 pipeline completo + retención) — **IMPLEMENTADO** (ver §5), Stripe completo (§10 repos/services/endpoints finales), notificaciones/SMTP (§11 repos/templates), categorías CRUD (§14 repos/endpoints), rate limiting (§18 implementación), tests críticos adicionales (§16).
- OpenAPI generado (`openapi.current.json`, `/docs`).
- Seguridad revisada: uploads validados (PDF/size), `safe_join` eliminado, CORS/timeouts/retries OK, rate limiting documentado pendiente.
- Tests: 149 pass / 0 fail; `test_retrieval_isolation` corregido.
- Pospuesto explícito: PII/anónimo completo (§5) — **IMPLEMENTADO** (ver §5), Stripe completo (§10), notificaciones/SMTP (§11), categorías CRUD (§14), rate limiting (§18).
- Documentación: `README.md`, `AGENTS.md`, `FRONTEND_API_INTEGRATION.md` actualizados; `CONTROL.md` eliminado por obsoleto; `borrar/` archivado.
- Criterio de cierre (§20): cumplido en todo lo implementado; puntos pospuestos documentados.

---
## Estado 2026-09-20 (sincronización documental con el código)

Reconciliación de este backlog contra el código real (verificación por archivo):

- **Stripe/billing completo (§10):** checkout, portal-session, create/cancel/reactivate/change-plan, sync-plan, GET subscription y webhook con firma + idempotencia (`stripe_eventos`) persisten en `pagos`/`comprobantes`/`suscripciones`/`suscripcion_historial`. Pendiente operativo: verificación e2e con checkout pagado, política de vencimiento/reintentos.
- **Platform `/api/platform/*` (§12):** implementado (12 rutas, `app/api/platform/routes.py`). Pendiente: CRUD de instituciones y CRUD de planes (hoy solo lectura + sync con Stripe).
- **Aislamiento (§2), RAG (§4), voz (§6), usuarios (§8), métricas (§13), categorías (§14):** ítems marcados `[x]` con nota **IMPLEMENTADO** y archivo de referencia; verificados en `retrieval_service.py`, `indexing_service.py`, `audio_service.py`, `admin_service.py`, `categories_service.py` y sus tests.
- **Sigue pendiente (sin marcar):** §1 Platform Admin (regla `/admin/*` requiere membresía + tests), §15 CI OpenAPI, §16 tests adicionales (rutas audit/config/categories/users/metrics/billing/audio/feedback), §17 QA manual multi-institución, §18 rate limiting, §11 notificaciones/SMTP, §12 CRUD instituciones/planes, `PUT /me`, lectura/moderación de feedback, descarga PDF original, exportación de auditoría/métricas/comprobantes, procesamiento asíncrono (Celery/Redis).
- `AGENTS.md`: sección "API actual" ampliada a las 46 rutas reales; FASE H y separación platform/admin corregidas.

---
## Estado 2026-09-20b (desbloqueo de features del Admin Dashboard)

Cambios backend que desbloquean pendientes del dashboard (verificados con tests):

- **`GET /api/admin/plans`** (§10): listado de planes activos y sincronizados con Stripe (`stripe_price_id`), para el selector de change-plan de Billing. `PlanOut` ahora incluye `stripe_product_id`/`stripe_price_id`. Tests: `tests/test_admin_plans_route.py`.
- **`MessageOut` con `sources`/`rating`/`feedback_comment`** (§6/§7): `GET /api/conversations/{id}` y `.../messages` devuelven los documentos recuperados (batch `message_documents` + títulos) y el feedback por mensaje. Desbloquea `ContextViewer`/`FeedbackBadge` del drawer. Tests: `tests/test_conversations_messages_context.py`.
- **Métricas de documentos/categoría** (§13): `GET /api/admin/metrics` (y `/api/platform/metrics`) devuelven `top_documents` y `documents_by_category` (dedupe por mensaje+documento, join a títulos/categorías). Desbloquea los 2 charts de Analytics. Tests: `tests/test_admin_service.py`.
- `openapi.current.json` regenerado con las nuevas rutas/campos; `FRONTEND_API_INTEGRATION.md` actualizado.
- Suite completa: **201 passed / 1 skipped / 1 deselected**.
- **Sigue pendiente**: notificaciones/SMTP (§11), rate limiting distribuido (§18), QA manual multi-institución (§17). *(CRUD instituciones/planes y exportaciones se cerraron en los estados 2026-09-20e/2026-09-20f.)*

---
## Estado 2026-09-20c (cierre de contrato — feedback, perfil y hardening de acceso)

- **`GET /api/admin/feedback`** (§6): moderación global paginada con filtros `conversacion_id`/`message_id`/`rating`; join a `mensajes` para `conversacion_id`/`contenido_texto`; aislamiento por institución. Tests: `tests/test_admin_feedback.py`.
- **`PUT /me`** (§1/§8): edición de perfil (`full_name`) vía `UsersRepository.update_user`; el resto de campos no es editable. Tests: `tests/test_put_me.py`.
- **Regla Platform Admin `/admin/*` (C1, §1)**: tests de ruta HTTP reales → 403 para platform admin sin membresía en documents/metrics/audit/users/config/feedback/plans (el guard corta antes de la DB); caso positivo con membresía. Tests: `tests/test_admin_platform_membership.py`.
- **CI OpenAPI (C5, §15)**: el check ya existía; se añadió artifact del diff al fallar y se marcó §15 completo.
- `openapi.current.json` regenerado con las 2 rutas nuevas; `FRONTEND_API_INTEGRATION.md` y `AGENTS.md` actualizados.

---
## Estado 2026-09-20d (hardening — C2 tests cross-tenant + C3 rate limiting)

- **C2 (tests cross-tenant de rutas, §2/§16)**: `tests/test_cross_tenant_admin.py` — con auth de la institución A: listas de audit/config/categories/users/feedback/billing/pagos/comprobantes/plans/documentos → 200 con items vacíos; `metrics` → total 0; recursos únicos (documento, subscription, plan, audio) → 404; `POST /api/chat/feedback` sobre mensaje ajeno → 404. Controles positivos con la institución de los datos (B) → 200. Fakes tenant-guardados emulan el filtrado real por `institucion_id`.
- **C3 (rate limiting, §18)**: variables documentadas en `.env.example` (`RATE_LIMIT_*`); nota explícita de que el token bucket es **in-memory por proceso** (no global con múltiples workers). Redis distribuido pospuesto explícitamente (suficiente para la tesis).

---
## Estado 2026-09-20e (CRUD platform — C4, §12)

- **CRUD de instituciones** (`POST/PUT/DELETE /api/platform/institutions[/{id}]`) y **CRUD de planes** (`POST/PUT/DELETE /api/platform/plans[/{id}]`): repos `InstitutionsRepository`/`BillingRepository` con create/update/deactivate (soft), schemas `InstitutionIn`/`PlanIn`, `PlatformService` con métodos, rutas con guard `require_platform_admin`. Deletes son soft-deactivate (`activo=false`) para no romper FKs (suscripciones `plan_id`, miembros/documentos `institucion_id`). Los planes se sincronizan con Stripe aparte (`sync-plan`).
- Tests: `tests/test_platform_crud.py` (guards 403 para admin institucional, CRUD 201/200/204, 404 cuando no existe, service-level con fakes).
- Suite completa: **230 passed / 1 skipped / 1 deselected**. `openapi.current.json` regenerado (49 rutas).

---
## Estado 2026-09-20f (exportaciones CSV)

- `GET /api/admin/audit/export`, `GET /api/admin/comprobantes/export`, `GET /api/admin/metrics/export`: reutilizan `AuditService`/`BillingService`/`AdminService`; respuesta `text/csv` + `Content-Disposition`; `metrics/export` con secciones (AGREGADOS, TOKENS POR MODELO, TOP DOCUMENTOS, DISTRIBUCION POR CATEGORIA, SERIE).
- Tests: `tests/test_admin_exports.py` (shape CSV + guard 403).
- Frontend: helper `exportCsv` + botones en Audit, Billing (Comprobantes) y Analytics.
- Suite completa: **234 passed / 1 skipped / 1 deselected**.

---
## Estado 2026-09-20g (notificaciones/SMTP — core, §11)

- **Core implementado**: repos `NotificationsRepository`/`SmtpConfigRepository`/`EmailTemplateRepository`; `NotificationService` (envío `smtplib` STARTTLS/SSL/TLS/NONE, render de plantillas con `{{placeholder}}`, persistencia con estados `PENDING/SENT/FAILED`, idempotencia por `clave_idempotencia`); endpoints `GET/PUT /api/admin/smtp` (precedencia institucional > global), `GET /api/admin/notifications` (paginado), `POST /api/admin/notifications/send-test`. Credencial global en env `SMTP_PASSWORD`.
- Tests: `tests/test_notifications.py` (rutas + guards 403 + service con fakes).
- **Diferido explícito**: CRUD de plantillas (`/api/admin/email-templates`) y triggers automáticos en el webhook Stripe (pago/vencimiento).
- Suite completa: **241 passed / 1 skipped / 1 deselected**.

---
## Estado 2026-09-20h (notificaciones extendidas + exports platform + UI)

- **Triggers en webhook Stripe**: `StripeWebhookService` inyecta `NotificationService`; notificaciones automáticas `PAYMENT_SUCCESS`/`PAYMENT_FAILED`/`SUBSCRIPTION_CANCELED`/`SUBSCRIPTION_EXPIRED`/`PLAN_CHANGED` con idempotencia `stripe-{event_id}-{tipo}` y fallo silencioso (no rompe el webhook). `NotificationService.send_automated` (sin auth). Tests: `tests/test_webhook_notifications.py`.
- **CRUD plantillas email**: `GET/POST/PUT/DELETE /api/admin/email-templates` (institucional > global; platform gestiona globales). Tests: `tests/test_email_templates.py`.
- **Exports platform**: `GET /api/platform/{audit,comprobantes,metrics}/export` + botones en `PlatformPage`. Util compartido `app/utils/csv_export.py` (refactor de admin).
- **UI SMTP/Notificaciones** en `SettingsPage` (dashboard): config SMTP + listado + envio de prueba.
- Suite completa: **258 passed / 1 skipped / 1 deselected**.

---
## Estado 2026-09-20i (backlog 1/3/10/16/18/19)

- **1**: deprecacion formal de `app_users.role` documentada en AGENTS (politica).
- **3 RLS**: documentado en `docs/RLS.md` (policies en DB real, service_role bypass, defensa en profundidad; revision periodica de policies pendiente en la DB).
- **10**: scripts `check_subscription_expiry.py` (vencimiento) y `reprocess_stripe_events.py` (reproceso de eventos fallidos).
- **16**: tests de webhook (idempotencia, payment_failed, deleted-CANCELLED, EXPIRED, dedupe de comprobante) y usuario `is_active=false` (`tests/test_security.py`, `tests/test_webhook_notifications.py`).
- **18**: `_validate_pdf` (MIME + magic-bytes `%PDF` + 50MB) aplicado tambien a `upload_new_version`; handler global de 500 (`main.py`) sin exponer detalles. Tests: `tests/test_security.py`.
- **19**: `README.md` actualizado (endpoints nuevos, env vars, secciones notificaciones/exports/rate limiting, storage corregido).
- Suite completa: **264 passed / 1 skipped / 1 deselected**.