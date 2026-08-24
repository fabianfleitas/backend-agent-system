# Plan de Sprints — Backend Asistente Institucional (reestructurado)

Estado base: cambios actuales + `pendientes_controlar.md` + `all_tables.json` completo (1342 líneas, 23 tablas). No se hizo `git commit`; este archivo precede ejecución.

---

## Regla transversal: Multiinstitución

Toda entidad con información institucional debe quedar asociada o derivada de una institución.

```
instancias / instituciones
  ├── usuarios (app_users + institucion_miembros)
  ├── categorías (categorias)
  ├── documentos (documentos + documento_versiones)
  ├── conversaciones (conversaciones + mensajes)
  ├── auditoría (audit_logs + pii_mappings)
  ├── feedback (feedback)
  ├── audio (audio_interactions)
  ├── suscripción / pagos (suscripciones + pagos + suscripcion_historial)
  ├── notificaciones (notificaciones)
  ├── planes / comprobantes / SMTP / PII
  └── stripe_eventos / pagos / suscripciones
```

Comprobar en: repositorios, servicios, endpoints, RLS, queries, dashboard (`admin/metrics`, `admin/users`, `admin/audit`). Aislamiento por `external_auth_id` + `institucion_id`.

---

## Estructura completa de tablas (23, de `all_tables.json`)

`app_users`, `audio_interactions`, `audit_logs`, `categorias`, `comprobantes`, `configuracion_smtp`, `conversaciones`, `document_chunks`, `document_embeddings`, `documento_versiones` (completo: status, es_version_activa, texto_extraido, total_chunks, indexed_at, error_message, file_size_bytes, cargado_por_external_auth_id), `documentos`, `feedback`, `institucion_miembros`, `instituciones`, `mensajes`, `message_documents`, `notificaciones`, `pagos`, `pii_mappings`, `planes`, `plantillas_email`, `stripe_eventos`, `suscripcion_historial`, `suscripciones`.

---

## Estado de implementación previa

- 🟢 RAG completo: PDF extractor, chunking, embeddings (`document_embeddings` vector), persistencia (`document_chunks`), retrieval (`retrieval_repository`), query embedding, guard dominio, OpenRouter (`openrouter_client`), prompt RAG, trazabilidad (`message_documents`), audit (`embedding_model`, `sources`).
- 🟢 OpenRouter implementado → Sprint 7: modelo configurable, costos, tokens, latencia, errores, fallback, métricas, evaluación, límites.
- 🟢 STT implementado (`stt_client`) → Sprint 7: validación de audio, límites duración, errores, métricas, WER, pruebas con distintos audios.
- 🟢 TTS implementado (`tts_client`) → Sprint 7: optimización/degradación graceful ya existe.

---

## Sprint 1 — Multiinstitución + Auth + RBAC + RLS

**Objetivo:** Supabase Auth + vinculación institucional + permisos backend + aislamiento.

**Mantener:** `app_users`, `instituciones`, `institucion_miembros`, `categorias`, `documentos`, `conversaciones`, `mensajes`, `audit_logs`, `feedback`, `audio_interactions` (todas con `institucion_id` / `external_auth_id`).

**Eliminar de Sprint 1 (no corresponde a arquitectura elegida):**
- `password_hash` propio
- `reset_token`, `reset_token_expires`
- `session_expires_at` como mecanismo propio
- recuperación de contraseña propia
- login propio
- política de contraseñas propia
- SMTP para recuperación

**Agregar:**
- Supabase Auth (`auth.users`) como fuente de identidad
- Google OAuth
- Vinculación `auth.users` → `app_users`
- Membresía institucional (`institucion_miembros`: `tipo_miembro`, `activo`, fechas)
- Contexto institucional (`institucion_id`) en repos/servicios
- Permisos backend (no ocultación de menús)
- RLS (Row Level Security) por `institucion_id` + `external_auth_id`
- Aislamiento entre instituciones
- Selección de institución cuando corresponda (dashboard)

**Flujo:**
```
Google / OAuth
  ↓
Supabase Auth → JWT
  ↓
Backend (`security.py`) → valida JWT + `external_auth_id`
  ↓
`app_users` (vinculado) → `institucion_miembros`
  ↓
RBAC (STUDENT / STAFF / ADMIN)
  ↓
RLS
```

**Entregable:** acceso multiinstitucional; membresía verificada; RLS activo; aislamiento comprobado.

---

## Sprint 2 — Dashboard administrativo + APIs

**Objetivo:** panel de administración con datos reales de instituciones, usuarios, documentos, auditoría y métricas.

**Tablas:** `app_users`, `instituciones`, `institucion_miembros`, `audit_logs`, `mensajes`, `feedback`, `documentos`, `documento_versiones`, `plan`/`suscripciones` si existe base.

**Endpoints/APIs:** `admin/documents`, `admin/reindex`, `admin/audit`, `admin/users`, `admin/metrics`; todos filtrados por `institucion_id` y `external_auth_id`.

**Entregable:** dashboard funcional; métricas agregadas; acceso restringido a ADMIN/STAFF; datos por institución.

---

## Sprint 3 — Suscripciones + planes

**Objetivo:** definir planes, límites funcionales, suscripciones e historial antes de Stripe.

**Tablas:** `planes` (codigo, nombre, descripcion, precio, moneda, intervalo, max_documentos, max_usuarios, max_estudiantes, features jsonb, stripe_product_id, stripe_price_id, activo); `suscripciones` (institucion_id, plan_id, estado, fecha_inicio, fecha_vencimiento, fecha_cancelacion, cancelacion_programada, stripe_subscription_id, stripe_customer_id, auto_renovacion, periodo_prueba_inicio/fin); `suscripcion_historial` (suscripcion_id, tipo_evento, plan_anterior_id/nuevo_id, estado_anterior/nuevo, descripcion, external_auth_id).

**Restricciones funcionales reales (no visuales):**
- Crear documento → ¿institución dentro de `max_documentos` de su `plan_id`? → rechazar o permitir.
- Crear usuario/estudiante → ¿dentro de `max_usuarios` / `max_estudiantes`?
- `features` (jsonb) gobierna funciones habilitadas (TTS, STT, RAG avanzado).

**Entregable:** planes configurados; suscripciones con ciclo; historial; límites funcionales activos.

---

## Sprint 4 — Stripe + pagos + webhooks

**Objetivo:** integración real de pasarela; webhooks como fuente confiable.

**Tablas:** `pagos`, `stripe_eventos` (`stripe_event_id` UNIQUE, tipo_evento, payload jsonb, procesado, procesado_at, error), `suscripciones`, `planes`.

**Implementar:** Stripe Checkout, Customers (`stripe_customer_id`), Subscriptions (`stripe_subscription_id`), Payment Intents, Webhooks, idempotencia (`stripe_event_id` UNIQUE; no procesar dos veces). Eventos críticos: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated/deleted`, `invoice.finalized`.

**Regla:** El frontend NO decide éxito de pago. Fuente confiable = Stripe webhook → `stripe_eventos` → procesamiento → actualización de `suscripciones` / `pagos`.

**Entregable:** pagos reales en sandbox; webhooks procesados; idempotencia verificada.

---

## Sprint 5 — Facturación + comprobantes

**Objetivo:** separar transacción de documento generado; comprobantes auditables.

**Tablas:** `pagos` (transacción: institucion_id, suscripcion_id, importe, moneda, estado, proveedor, stripe_payment_intent_id/checkout_session/charge, idempotency_key, descripcion, fecha_pago); `comprobantes` (institucion_id, pago_id, tipo_comprobante, numero, estado, importe, moneda, archivo_path, proveedor, referencia_externa, fecha_emision, created_at).

**Importante:**
- `Pago` ≠ `Comprobante` ≠ `Factura legal`
- Comprobantes: generar, numeración, fecha, institución, pagador, detalle, importe, moneda, método pago, referencia Stripe, estado, archivo, reimpresión, anulación.
- No modificar físico sin anulación + nueva emisión; registrar trazabilidad.

**Entregable:** comprobantes generados con referencia a pago; archivo guardado; estados controlados; anulación/reimpresión auditada.

---

## Sprint 6 — Notificaciones + vencimientos

**Objetivo:** motor de notificaciones basado en suscripción; SMTP exclusivo para notificaciones.

**Tablas:** `notificaciones` (institucion_id, suscripcion_id, tipo, canal, destinatario, asunto, contenido, estado, fecha_programada, fecha_envio, error, clave_idempotencia), `suscripciones` (fecha_vencimiento, cancelacion_programada), `plantillas_email`, `configuracion_smtp`.

**SMTP (moved from Sprint 2):** usado exclusivamente para vencimientos, pagos, renovación, cambio plan, comprobantes, errores.

**Motor:**
- `suscripcion` → `fecha_vencimiento`
- Scheduler → 7 días / 3 días / 1 día / 0 días / vencida
- Notificaciones: próxima a vencer, vencida, pago aprobado/rechazado, renovación, cambio plan, cancelación, comprobante generado.
- `clave_idempotencia` para evitar duplicados.

**Entregable:** notificaciones programadas; SMTP configurado sin exponer credenciales; idempotencia activa.

---

## Sprint 7 — Calidad RAG + Voz + Métricas + Evaluación

**Objetivo:** RAG y voz ya implementados; se evalúan y optimizan.

**RAG (COMPLETADO → optimización):** calidad retrieval, similarity threshold, precisión, recall, RAG hit rate, fuentes (`sources`), evaluación LLM-as-a-Judge, costos, tokens, latencia, respuestas fuera de contexto, fidelidad (`score_fidelidad/relevancia/contexto`).

**OpenRouter (COMPLETADO → optimización):** modelo configurable, costos, tokens, latencia, errores, fallback, métricas, evaluación, límites de uso.

**STT (COMPLETADO → validación):** validación de audio, límites duración, errores, métricas, WER, pruebas con distintos audios.

**TTS (COMPLETADO → optimización):** degradación graceful existente.

**Tablas:** `audit_logs` (métricas de calidad), `message_documents` (`similarity_score`), `mensajes` (tokens, tiempo, modelo), `audio_interactions` (duración, formato, modelo), `feedback`.

**Entregable:** métricas de calidad RAG y voz; evaluación de respuestas; límites de uso; optimización de costos.

---

## Sprint 8 — Seguridad + Testing + Producción

**Objetivo:** seguridad institucional, pruebas negativas, calidad de código, documentación, producción.

**Tablas:** `app_users`, `institucion_miembros`, `audit_logs`, `pii_mappings`, `feedback`, `mensajes`, `comprobantes`.

**Cobertura:**
- Protección formularios públicos (CAPTCHA/reCAPTCHA + sanitización + límite IP + registro eventos)
- Pruebas negativas (vacíos, formatos incorrectos, repetición, sin permisos, URLs expiradas, archivos no permitidos, cantidades negativas, duplicados)
- Acceso por URL según rol; aislamiento entre instituciones; usuario inactivo bloqueado
- Borrado lógico (`hidden`, `is_active`, `status`, `es_version_activa`)
- Auditoría inmutable; mensajes sin info técnica; hashing seguro
- Calidad código: eliminar duplicados, variables claras, sin debugs, código comentado útil
- Migraciones versionadas; índices creados; datos iniciales controlados
- Política privacidad + consentimiento (`app_users` + evidencia de aceptación/revocación)
- Recibos / comprobantes con identificación única, datos emisor/pagador, detalle, monto, forma pago, trazabilidad, leyenda
- Documentación instalación (README, `.env`, comandos, versiones, datos iniciales)
- Métricas verificables (carga <3s, expiración definida, concurrencia)
- No información fija en código (tasas, límites, textos, expiración)

**Entregable:** sistema validado; documentos completos; producción lista.

---

## Verificación por sprint (tablas y servicios)

| Sprint | Tablas / entidades centrales | Repos / servicios | RAG / Voz / OR | Pendientes clave |
|---|---|---|---|---|
| 1 | `app_users`, `instituciones`, `institucion_miembros`, `categorias` | `users`, `security`, RLS | — | 2, 25, 27 |
| 2 | `app_users`, `audit_logs`, `mensajes`, `feedback`, `documentos` | `admin_service`, `chat_service` | — | 7, 8, 21, 22 |
| 3 | `planes`, `suscripciones`, `suscripcion_historial` | `subscription_service` | — | 9, 10, 11, 12 |
| 4 | `pagos`, `stripe_eventos`, `suscripciones` | Stripe clients, webhooks | — | 14 |
| 5 | `comprobantes`, `configuracion_smtp`, `plantillas_email` | `mail_service` | — | 15, 16, 36 |
| 6 | `notificaciones`, `suscripciones`, `configuracion_smtp`, `planes` | `notification_service` | — | 13 |
| 7 | `audit_logs`, `message_documents`, `mensajes`, `audio_interactions`, `feedback`, `document_embeddings` | `retrieval/embedding/indexing`, `audio_service` | 🟢 COMPLETADO → evaluación | 18 (validación), evaluaciones |
| 8 | Todos | `tests/`, docs | — | 26, 31, 32, 35, 34, 6, 19, 20, 30, 29, 33, 36 |

---

## Recomendaciones finales (12 puntos)

1. Multiinstitución es transversal: todos los repos/queries incluyen filtro por `institucion_id`; RLS protege `documentos`, `conversaciones`, `audio_interactions`, `audit_logs`, `feedback`, `suscripciones`, `pagos`, `notificaciones`.
2. `stripe_eventos` pieza central con `stripe_event_id` UNIQUE e idempotencia; webhook = fuente confiable.
3. No confundir `Pago` (transacción Stripe) con `Comprobante` (documento generado) ni con `Factura legal`; cada tabla su función.
4. SMTP (`configuracion_smtp`) solo para notificaciones/comprobantes; nunca autenticación ni recuperación contraseña.
5. RAG, OpenRouter, STT, TTS ya implementados; Sprint 7 = evaluación (calidad, métricas, costos, WER), no construcción.
6. Restricciones de plan (`max_documentos/usuarios/estudiantes`, `features`) deben ser lógica funcional real en repos/servicios.
7. `message_documents` vincula `mensaje_id` + `audit_id` + `chunk_id` + `similarity_score`; trazabilidad completa.
8. `pii_mappings` vinculado a `audit_id`; no exponer `original_value` sin necesidad.
9. `audio_interactions` guarda rutas locales protegidas (`safe_join`); nunca URLs públicas.
10. `comprobantes` requiere referencia a pago; anulación = nueva emisión con nuevo número; sin modificación física.
11. Datos iniciales controlados (`instituciones`, `planes` base, `categorias`, admin) por script.
12. Mantener `FRONTEND_API_INTEGRATION.md` sincronizado; usar `AGENTS.md` como guía.

---

## Dudas / Aclaraciones requeridas antes de iniciar

1. ¿Confirmás estructura de 8 sprints propuesta (multiinstitución → dashboard → planes → Stripe → facturación → notificaciones → calidad RAG/voz → seguridad)?
2. ¿Supabase Auth + Google OAuth ya habilitado o requiere configuración?
3. ¿RLS con políticas Supabase directas o capa de repos (filtrado explícito)?
4. ¿Límites de plan (`max_documentos`, etc.) funcionales con rechazo, o solo informativos?
5. ¿Stripe sandbox o cuentas reales? ¿`stripe_eventos` todos los eventos o solo críticos?
6. ¿Notificaciones: canal `email` obligatorio o `in_app` también? ¿Programación dinámica por `fecha_vencimiento`?
7. ¿Consentimiento privacidad: página pública con checkbox no seleccionado por defecto, o registro `app_users`?
8. ¿Purga periódica de `audit_logs` o conservación indefinida?
9. ¿`feedback` obligatorio vinculado a `audit_id` o independiente?
10. ¿Confirmás que RAG, OpenRouter, STT, TTS no requieren implementación, solo evaluación Sprint 7?

---

## Confirmación de dudas (Sprint 1 autorizado)

- Estructura 8 sprints: confirmada.
- Supabase Auth + Google OAuth: habilitado/configurado (Sprint 1 procede sin bloqueo).
- RLS: políticas Supabase directas ya existentes.
- Límites de plan (`max_documentos/usuarios/estudiantes`): informativos (no rechazar creación en este sprint; se implementará restricción real en Sprint 3 si se requiere).
- Stripe: sandbox; `stripe_eventos` críticos; webhook fuente confiable.
- Notificaciones: programación dinámica por `fecha_vencimiento`; canal email + `in_app` si aplica; `clave_idempotencia` activa.
- Consentimiento privacidad: ignorado para front (manejable en frontend); no bloquea Sprint 1.
- `audit_logs`: conservación indefinida (sin purga periódica).
- `feedback`: vinculación a `audit_id` pendiente de definir; no bloquea Sprint 1.
- RAG / OpenRouter / STT / TTS: implementados; Sprint 7 = evaluación/optimización.

**Estado:** Sprint 1 autorizado. Multiinstitución + Auth + RBAC + RLS inicia.

---

*Plan actualizado con estructura completa de tablas (`all_tables.json`). Confirmar dudas → proceder Sprint 1.*
