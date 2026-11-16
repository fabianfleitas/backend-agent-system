# Evidencia de pruebas — backend-agent-system

Documento de evidencia para la tesis (§4.5 / §5.1.3). Distingue resultados
históricos, verificaciones locales actuales y evaluaciones que todavía no se han
realizado.

## Resumen

| Campo | Valor |
|---|---|
| Fecha de la corrida archivada | 2026-09-22 |
| Repositorio | `backend-agent-system` |
| Framework de pruebas | `pytest` |
| Comando | `python3 -m pytest` |
| Resultado histórico | **369 passed · 0 skipped · 2 deselected** (integración con Stripe real marcada `integration`, excluida por defecto; no representa la suite actual) |
| CI | `.github/workflows/ci.yml` — pytest en Python 3.10/3.11/3.12 + verificación del contrato OpenAPI (`scripts/generate_openapi.py --check`) |
| Contrato API | `openapi.current.json` sincronizado (`generate_openapi.py --check` OK) |

## Verificaciones locales actuales (2026-11-08)

- Suite completa de backend: **386 passed** en Python 3.12.16 (2026-11-08; 37
  avisos/deprecaciones, sin fallos) y **386 passed** con Python 3.9.6 (40 avisos),
  aunque esa versión no es la requerida. Incluye pruebas para consentimiento
  ausente/falso, fallo de auditoría antes de proveedores externos y regresión PII.
- `student-module`: 20 pruebas Vitest pasaron; `npm run build` y `npm run lint`
  pasaron. Son verificaciones locales, no pruebas con backend desplegado.
- Contrato OpenAPI: `python3 scripts/generate_openapi.py --check` pasó.
- PII sintético: 120/120 casos, 295/295 valores personales esperados protegidos,
  cero fugas, cero detecciones no esperadas; evidencia detallada en
  `eval/reports/pii_20261108_170839_266425.json` (Python 3.12.16, spaCy
  `es_core_news_md` 3.8.0).
- Ajuste PII: exclusión exacta de `Necesito` solo cuando Presidio lo clasifica como
  `LOCATION` o `PERSON` en español. No se bajó la cobertura mediante un umbral
  global más alto.
- Entorno local: Python 3.12.16, k6 2.3.0, Supabase CLI 3.0.0, Docker CLI 29.9.3
  y Colima 0.10.3. Docker Desktop no se pudo instalar porque exigía contraseña de
  administrador; Colima se usó como daemon local. No se desplegó nada en producción.
- Se creó un bootstrap local aislado (`eval/local_supabase_schema.sql`) y un seed
  sintético (`eval/seed_local_synthetic.py`); no se modificaron las migraciones
  existentes ni se usaron datos reales. La decisión es mantenerlo como fixture
  local, no como migración de producción.
- Los reportes de esta fecha se copiaron a `docs/evidencias/2026-11-08/`, porque
  `eval/reports/` está excluido de Git. Esa copia incluye hashes SHA-256.
- Carga HTTP local ejecutada con Supabase local, institución y usuario sintéticos,
  `LLM_ENABLED=false`, `EMBEDDINGS_ENABLED=false`, `JUDGE_ENABLED=false`,
  STT/TTS desactivados. Las consultas devolvieron respuestas mock.
- Las pruebas de carga anteriores usaron respuestas mock. Después se ejecutó un
  A/B real con LLM/embeddings/juez, documentado más abajo. Estas mediciones siguen
  sin demostrar capacidad de producción ni el SLO de 3 s.
- El primer intento de WER quedó bloqueado por HTTP 402. Tras cargar créditos se
  completó sobre los 6 audios: WER macro 1,52 % y de corpus 1,75 %. No hubo
  llamadas TTS nuevas.

## Carga HTTP local sintética (2026-11-08)

Medición con k6 2.3.0 contra `127.0.0.1`, base Supabase local y usuario/institución
sintéticos. La configuración fue `LLM_ENABLED=false`, `EMBEDDINGS_ENABLED=false`,
`JUDGE_ENABLED=false`, STT/TTS desactivados y `RATE_LIMIT_ENABLED=false` para los
escenarios de capacidad. Las conversaciones se prepararon antes de la medición.

| Escenario | Solicitudes de chat | Respuestas 200 | P50 exitosas | P95 exitosas |
|---|---:|---:|---:|---:|
| 1 VU | 100 | 100 | 17.2 ms | 18.4 ms |
| 8 VUs | 104 | 104 | 59.4 ms | 69.8 ms |
| 50 VUs | 100 | 100 | 389.5 ms | 582.1 ms |
| 100 VUs | 100 | 100 | 708.6 ms | 801.4 ms |

Cada escenario es un burst de ~100 solicitudes, no una prueba sostenida. Los
valores corresponden a respuestas mock sin retrieval, LLM ni juez. **No equivalen a
la latencia del pipeline real ni al SLO de 3 s.** Reporte agregado:
`eval/reports/local_validation_20261108.json`; exportaciones k6:
`eval/reports/k6_local_{1,8,50,100}vu.json`.

Prueba separada con rate limit activo y 8 VUs: 104 solicitudes de chat, **20
respuestas 200 y 84 respuestas 429** (19,23 % de éxito). El archivo crudo
`eval/reports/k6_local_8vu_rate_limit_raw.json` permitió contar los códigos
directamente. Esto demuestra que el límite por IP de 20 solicitudes/minuto produce
429 cuando la carga lo supera. No permite atribuir por sí solo la causa de los
fallos históricos de 8 usuarios, porque aquellos reportes no conservaron los
códigos HTTP.

### Carga sostenida local

Se añadió `eval/k6_sustained.js` y `eval/run_sustained_local.py`. Corrida del
2026-11-08: 8 VUs, 30 iteraciones por VU, pausa de 1 s, **240 solicitudes de chat**
durante ~36 s y `RATE_LIMIT_ENABLED=false`.

- 240/240 respuestas `200`.
- P50 68,5 ms; P95 271,2 ms; promedio 192,9 ms; máximo aislado 3.606,9 ms.
- Muestras del proceso backend: CPU `ps` promedio 16,44 %, máximo 103,1 %; RSS
  máximo 1.796,1 MB.
- Reportes: `eval/reports/k6_sustained_20261108_173901_391454.json` y
  `eval/reports/k6_sustained_20261108_173901_391454_result.json`.

Sigue siendo una prueba con respuestas mock y sin retrieval/LLM/juez. La latencia
máxima superó 3 s en una solicitud, aunque el P95 no; no se debe extrapolar a
producción. Los reportes se conservaron también en
`docs/evidencias/2026-11-08/` porque `eval/reports/` está ignorado por Git.

## RNF-05 — prueba definitiva (2026-11-08)

La configuración adoptada es `openai/gpt-oss-20b` vía OpenRouter, proveedor
**Groq** forzado (`allow_fallbacks=false`), razonamiento **low**,
`llm_max_tokens=384`, `retrieval_match_count=4` y juez fuera. Sobre **100
observaciones (2 × 50)** en local:

- P50 **1.502 ms**; P95 **2.089 ms**; máximo 5.735 ms.
- 100/100 respuestas 200; 0 errores; 100/100 fuentes esperadas.
- **RNF-05 se cumple** (p95 ≤ 3 s) en el entorno local.

Evidencia: `docs/evidencias/2026-11-08/rnf05_local_20261108.md`,
`rnf05_local_20261108_100obs.json`, `rnf05_local_384_4_A_20261108.json` y
`rnf05_local_384_4_B_20261108.json`.

## A/B juez OFF/ON (RF-52, histórico)

Se ejecutaron las mismas 25 preguntas del Gold Dataset en dos condiciones, con
conversaciones aisladas, corpus sintético indexado y Supabase local:

- LLM y juez (histórico): `openai/gpt-4o-mini`.
- Embeddings: `text-embedding-3-small` (OpenAI directo).
- Juez OFF y ON en corridas separadas; 25 solicitudes de chat por condición.
- 25/25 respuestas `200` y 25/25 fuentes esperadas recuperadas en cada condición.

| Condición | P50 | P95* | Máximo | Tokens entrada | Tokens salida |
|---|---:|---:|---:|---:|---:|
| Juez OFF | 2.176,2 ms | 3.935,7 ms | 5.394,7 ms | 18.956 | 1.589 |
| Juez ON | 4.188,8 ms | 7.090,0 ms | 7.237,6 ms | 18.956 | 1.579 |

\* P95 calculado sobre 25 observaciones; es indicativo, no un percentil robusto
de producción. La mediana del incremento pareado por pregunta fue **+1.842,9 ms**
y el promedio **+1.922,3 ms** al activar el juez.

Con juez ON se obtuvieron 25 evaluaciones automáticas: fidelidad **0,996**,
relevancia **1,0** y contexto **1,0**. Son puntuaciones del juez, **no revisión
humana**. La muestra sigue siendo pequeña y el corpus es sintético.

Evidencia: `eval/reports/ab_judge_20261108.json`,
`eval/reports/eval_20261108_175752_280723.json` (OFF),
`eval/reports/eval_20261108_175956_080905.json` (ON) y copia en
`docs/evidencias/2026-11-08/`. Las dos planillas de revisión humana están vacías;
completarlas sigue pendiente.

## Evaluación de voz (2026-11-08)

Se ejecutó el WER sobre los 6 audios TTS existentes con `x-ai/grok-stt-1.0`:

- **WER macro: 1,52 %**.
- **WER corpus: 1,75 %** (1 palabra de diferencia sobre 57 palabras de referencia).
- g01: 9,09 % por `ingresantes` → `ingresante`; g02–g06: 0 %.
- Reporte: `eval/reports/wer_20261108_181549_631213.json` y copia en
  `docs/evidencias/2026-11-08/`.

Es una muestra pequeña de audio TTS limpio y no sustituye una evaluación con voz
humana, micrófonos y ruido ambiente normal. El intento inicial quedó bloqueado
por HTTP 402 por falta de créditos; se conserva como antecedente, pero el WER
posterior sí pudo completarse.

## Calidad de respuestas y encuesta de validación

- Los promedios históricos del LLM-as-a-Judge no tienen una revisión humana
  independiente documentada; no deben presentarse como precisión o calidad
  validada. La corrida real de 25 preguntas actualiza la evidencia automática,
  pero tampoco sustituye la revisión humana.
- No hay en este repositorio evidencia verificable de una encuesta formal de
  validación (instrumento, muestra y respuestas). La plantilla de revisión humana
  prevista por `eval.run_eval.py`, mientras esté vacía, no representa validación.
- La cifra previamente citada de usabilidad (3,77/5; 65 % favorable) se conserva
  únicamente como dato histórico pendiente de fuente primaria y metodología. No
  se considera verificada por este documento.
- Plan y protocolo: `docs/PLAN_VALIDACION_TECNICA.md`.

## Áreas cubiertas por la suite

- Autenticación y autorización: `test_auth_context.py`, `test_auth_edge.py`, `test_security.py`, `test_roles.py`, `test_admin_role_granularity.py` (ADMIN vs SECRETARIA).
- Aislamiento multi-institución: `test_isolation.py`, `test_cross_tenant_*`, `test_retrieval_isolation.py`, `test_admin_platform_membership.py`, `test_membresia_unica.py`.
- Chat y pipeline RAG: `test_chat_service.py`, `test_conversations_messages_context.py`, `test_retrieval_service.py`, `test_generation_service.py`.
- PII / anonimización / desanonimización: `test_pii_service.py`, `test_pii_pipeline.py` (incluye cédula paraguaya y restauración local).
- LLM-as-a-Judge: `test_judge_service.py`, `test_chat_service.py` (scores en `audit_logs`).
- Derivación a operador (escalamientos): `test_handoff_service.py`, `test_chat_service.py` (handoff ante guard).
- Gestión documental: `test_documents_validation.py`, `test_document_download.py`, `test_chunking_service.py`, `test_embedding_service.py`, `test_indexing_service.py`, `test_categories*.py`.
- Billing / Stripe: `test_billing_read.py`, `test_stripe_*` (checkout, portal, suscripción, change-plan, webhook), `test_admin_plans_route.py`.
- Admin (dashboard): `test_admin_conversations.py`, `test_admin_exports.py`, `test_admin_feedback*.py`, `test_admin_service.py`, `test_admin_platform_membership.py`, `test_platform_*`.
- Salud del sistema: `test_health.py`, `test_openapi_contract.py`, `test_rate_limit.py`.

## Mapeo requerimiento → evidencia

| Requerimiento | Evidencia |
|---|---|
| RF-02 Anonimización / PII (cédula paraguaya) | `test_pii_service.py`, `test_pii_pipeline.py` |
| RF-03 RAG (recuperación con fuentes) | `test_retrieval_service.py`, `test_chat_service.py` |
| RF-04 Desanonimización local | `test_pii_service.py` (restore), `test_pii_pipeline.py` (DEANON) |
| RF-05 Gestión de feedback | `test_feedback_route.py`, `test_admin_feedback.py`, `test_admin_feedback_moderation.py` |
| RF-06 Gestión de conversaciones | `test_conversations_messages_context.py`, `test_admin_conversations.py` |
| RF-07 Voz (STT/TTS) | `test_transcription_service.py`, `test_synthesis_service.py`, `test_chat_voice_route.py` |
| RF-08 Persistencia local y caché | `test_persistence.py`, `test_cache_settings.py`, `test_feedback_route.py` |
| RF-52 Evaluación automática (no validación humana) | `test_judge_service.py`, `test_chat_service.py` (scores); revisión humana pendiente |
| RF-53 Derivación de consultas a Secretaría | `test_handoff_service.py`, `test_chat_service.py` (HANDOFF) |
| RNF-02 RBAC (roles) | `test_admin_role_granularity.py`, `test_security.py`, `test_roles.py` |
| RNF-08 Trazabilidad/auditoría | `test_audit_service.py`, `test_chat_service.py` (audit_logs) |
| Aislamiento institucional | `test_cross_tenant_*`, `test_isolation.py` |

## Pendientes (manuales / no automatizados)

- `admin-dashboard/QA_CHECKLIST.md`: validación manual contra backend real (requiere app corriendo). Pendiente de marcar.
- A/B juez ON/OFF real: ejecutado con 25 preguntas por condición. La comparación de **calidad** con revisión humana sigue pendiente.
- Carga k6 en staging/producción y métricas de despliegue/uptime: pendientes; ver `docs/PLAN_VALIDACION_TECNICA.md` y `eval/README.md`.
- WER nuevo: completado sobre 6 audios TTS; falta ampliar con voz humana y condiciones normales.
- Revisión humana de calidad y encuesta formal de validación: no realizadas/documentadas en esta evidencia.
- Integraciones reales marcadas `integration` (ej. checkout Stripe en vivo) quedan excluidas de la corrida por defecto.

---

*Generado para la comparación sistemática tesis ↔ sistema (Parte 5).*
