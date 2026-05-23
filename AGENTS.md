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
- **Configuracion:** `pydantic-settings`, lee `.env` desde la raiz del proyecto
- **Persistencia actual:** en memoria mediante `app/services/mock_store.py` (singleton `store`)
- **RAG / IA / STT / TTS:** no implementados realmente; las rutas actuales usan respuestas mock
- **Procesamiento asincrono:** no implementado; `Celery`/`Redis` aun no existen en el codigo
- **Base de datos:** no existe todavia; no hay SQLAlchemy, PostgreSQL, pgvector ni Alembic en uso
- **Testing:** no existe directorio `tests/`

## Arquitectura objetivo

Segun `requisitos.md`, `documentacion.md` y `modelo_inicial_datos.md`, el sistema
debe evolucionar hacia:

- **RAG desde el inicio:** indexacion documental, embeddings, recuperacion de contexto y prompts contextualizados
- **Persistencia real:** historial permanente, audios, documentos, auditoria y embeddings
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
- Mantener modulos desacoplados: RAG, voz, IA, historial y documentos

## Entrypoint

`app/main.py:create_app()` es el factory principal; no reemplazarlo por una
instancia plana de `FastAPI()`.

Run:

`uvicorn app.main:app --reload`

## Auth delegada

No usar JWT propio mientras no sea un requerimiento explicito.

Todos los endpoints de negocio dependen de headers delegados:

- `X-External-Auth-Id` es obligatorio
- `X-Auth-Provider` es opcional; por defecto `delegated`
- `X-User-Type` permite `ESTUDIANTE`, `ADMIN`, `SECRETARIA`
- `X-User-Email` es opcional

La extraccion del contexto se hace en `app/core/security.py:get_auth_context()`.
Los endpoints administrativos deben pasar por `require_admin()`.

## API actual

Rutas expuestas hoy:

```text
/api/student/query                 POST
/api/student/voice-query           POST
/api/student/history               GET
/api/student/history/{id}/hide     PATCH
/api/admin/documents               POST
/api/admin/documents               GET
/api/admin/reindex                 POST
/api/admin/audit                   GET
/health                            GET
```

Notas:

- La ruta de salud actual es `/health`, no `/api/health`
- `student/query` y `student/voice-query` aun responden con contenido mock
- `admin/documents` persiste archivos en disco, pero el metamodelo sigue siendo in-memory
- `admin/reindex` solo cambia estado mock; no genera embeddings reales

## Persistencia actual vs objetivo

### Actual

- Conversaciones, mensajes, audio metadata, documentos, versiones y auditoria viven en memoria
- Si el proceso reinicia, se pierde el estado del `store`
- Los archivos subidos se guardan en `storage/`, pero sus metadatos no son persistentes reales

### Objetivo

El modelo esperado incluye al menos estas entidades conceptuales:

- usuario
- conversacion
- mensaje
- audio_interaccion
- documento
- documento_version
- embedding
- mensaje_documento
- log_auditoria

Usar `modelo_inicial_datos.md` como guia funcional, no como reflejo exacto del codigo ya implementado.

## Estructura relevante

- `app/main.py`: factory FastAPI y startup
- `app/api/router.py`: router principal
- `app/api/student/routes.py`: endpoints de alumnos
- `app/api/admin/routes.py`: endpoints administrativos
- `app/core/config.py`: settings
- `app/core/security.py`: auth delegada y control de roles
- `app/services/mock_store.py`: almacenamiento temporal en memoria
- `app/utils/files.py`: helpers seguros para escritura y rutas

## Convenciones

- Preferir `from __future__ import annotations` en archivos Python nuevos o modificados
- Modelos de dominio actuales: `@dataclass`
- Schemas de entrada/salida: `pydantic.BaseModel`
- Para escritura de archivos usar `app/utils/files.py`
- Usar `safe_join()` para evitar path traversal
- Ejecutar `ensure_dir()` antes de escribir en disco
- El startup crea `storage/`, `storage/audio/` y `storage/documents/`

## Dependencias

### Actuales

- `fastapi`
- `uvicorn[standard]`
- `python-multipart`
- `pydantic-settings`

### Objetivo futuro

Agregar dependencias solo cuando se implemente realmente la capacidad asociada:

- persistencia relacional
- vector store / embeddings
- OpenRouter u otros proveedores IA
- Whisper o STT/TTS equivalente
- Celery / Redis
- testing automatizado

## Prioridades de implementacion

Si vas a extender el sistema, prioriza en este orden:

1. Persistencia real de historial, documentos, auditoria y audio metadata
2. Gestion documental con versionado real
3. Pipeline RAG real con trazabilidad por documentos usados
4. Integracion real con OpenRouter
5. STT/TTS real para consultas de voz
6. Workers asincronos para tareas pesadas
7. Observabilidad, metricas y pruebas automatizadas

## Notas para agentes

- No asumir que "funciona" porque exista un endpoint; varios flujos son mocks
- No introducir una base de datos o librerias grandes sin actualizar primero las dependencias
- No romper el aislamiento por `external_auth_id`
- No convertir el ocultamiento de historial en borrado fisico
- No responder preguntas fuera del dominio institucional una vez se implemente el flujo IA real
