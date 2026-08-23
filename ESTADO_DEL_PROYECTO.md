# Estado del Proyecto

**Fecha:** 2026-08-22

Este archivo resume el estado real del backend en este momento. Sirve como
snapshot operativo para distinguir con claridad entre lo que ya está
implementado y lo que todavía sigue en evolución.

## Resumen ejecutivo

El backend ya no es solo un esqueleto con mocks: ahora tiene persistencia real
parcial en Supabase, chat con retrieval real, integración con OpenRouter,
transcripción STT, síntesis TTS, gestión documental con carga/versionado e
indexación, además de trazabilidad para auditoría y feedback.

Aun así, el sistema sigue en transición. Hay flujos que dependen de flags y
degradan a comportamiento mock o controlado si el proveedor no responde o si la
capacidad está deshabilitada.

## Implementado hoy

- FastAPI como framework principal.
- Factory principal en `app/main.py:create_app()`.
- Autenticación delegada por headers.
- `/me` con persistencia real en Supabase.
- `/ready` con chequeo real parcial de Supabase y storage.
- Conversaciones persistidas.
- Mensajes persistidos.
- Documentos y versiones persistidos.
- Metadata de audio persistida.
- Feedback persistido.
- Auditoría persistida.
- Trazabilidad RAG persistida en `message_documents`.
- Carga de PDFs desde administración.
- Versionado documental.
- Reindexación de documentos.
- Retrieval real cuando `EMBEDDINGS_ENABLED=true`.
- Generación real con OpenRouter cuando `LLM_ENABLED=true`.
- Transcripción real cuando `STT_ENABLED=true`.
- Síntesis real cuando `TTS_ENABLED=true`.
- Métricas administrativas agregadas desde auditoría y trazabilidad.
- Tests en desarrollo dentro de `tests/`.

## Estado por capacidad

### Chat de texto

- Recupera contexto real cuando el pipeline de embeddings está activo.
- Usa memoria conversacional cuando `LLM_HISTORY_ENABLED=true`.
- Genera respuesta real con OpenRouter cuando `LLM_ENABLED=true`.
- Si no hay contexto suficiente, devuelve guard de dominio.
- Si el LLM falla, devuelve un fallback controlado.

### Chat por voz

- Transcribe audio real cuando `STT_ENABLED=true`.
- Si STT falla con el flag activo, devuelve `503`.
- Alimenta la transcripción al mismo pipeline de chat de texto.
- Sintetiza audio de respuesta cuando `TTS_ENABLED=true`.
- Si TTS falla, conserva la respuesta textual y registra la incidencia.

### Gestión documental

- Sube archivos PDF.
- Crea documentos y versiones.
- Guarda archivo físico en storage.
- Extrae texto o indexa según `EMBEDDINGS_ENABLED`.
- Reindexa versiones activas.

### Administración

- Lista usuarios.
- Lista documentos.
- Consulta auditoría.
- Expone métricas agregadas.

## Persistencia actual

Hoy persisten en Supabase:

- usuarios actuales
- conversaciones
- mensajes
- documentos
- documento_versiones
- audio_interactions
- audit_logs
- feedback
- message_documents

Los archivos siguen viviendo en storage local del proyecto para el entorno actual.

## Dependencias funcionales

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `LLM_ENABLED`
- `STT_ENABLED`
- `TTS_ENABLED`
- `EMBEDDINGS_ENABLED`

## Pendientes principales

- Procesamiento asincrono con workers.
- Persistencia completamente homogénea en todos los flujos documentales.
- Observabilidad más completa.
- Pruebas automatizadas más amplias.
- Evolución futura a tiempo real con WebSockets/WebRTC.

## Riesgos a tener presentes

- No asumir que un endpoint ya cubre toda la capacidad final.
- No confundir fallback controlado con implementación completa.
- No romper el aislamiento por `external_auth_id`.
- No tratar rutas internas de storage como URLs públicas.
- No convertir ocultamiento de historial en borrado físico.

## Documentos relacionados

- [README.md](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/README.md)
- [AGENTS.md](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/AGENTS.md)
- [FRONTEND_API_INTEGRATION.md](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/FRONTEND_API_INTEGRATION.md)
- [tables.sql](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/tables.sql)
- [requisitos.md](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/requisitos.md)
- [modelo_inicial_datos.md](/Users/ServiciosDigitales/Documents/fabian/projects/backend-agent-system/modelo_inicial_datos.md)

