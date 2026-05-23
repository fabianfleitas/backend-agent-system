# Requisitos de Refactor y Ajustes del Backend API (Fase Mock/MVP)

## Objetivo General

Refactorizar y estabilizar la arquitectura del backend FastAPI antes de integrar:

* RAG real
* LangChain
* Whisper
* embeddings
* anonimización
* IA real

El objetivo es dejar:

* contratos API definitivos
* estructura REST consistente
* separación correcta de responsabilidades
* soporte RBAC
* compatibilidad futura con RAG y auditoría

---

# 1. Reestructuración de Endpoints

## 1.1 Eliminar prefijo `/student`

### Problema

Actualmente existen endpoints como:

```text
/api/student/*
```

Esto acopla la API a un rol específico.

---

## Requisito

Reemplazar endpoints de usuario final por rutas neutrales.

---

## Cambios requeridos

### Antes

```text
/api/student/query
/api/student/voice-query
/api/student/conversations
```

---

### Después

```text
/api/chat/query
/api/chat/voice
/api/conversations
```

---

## Justificación

Los endpoints representan funcionalidades del sistema, no roles.

La autorización debe resolverse mediante:

* JWT
* RBAC
* middleware

NO mediante naming de rutas.

---

# 2. Crear Endpoint Principal de Chat

## Requisito

Implementar endpoint centralizado para consultas RAG.

---

## Endpoint requerido

```http
POST /api/chat/query
```

---

## Request esperado

```json
{
  "conversation_id": 1,
  "message": "¿Cuándo inician los exámenes?"
}
```

---

## Response esperado

```json
{
  "response": "Los exámenes inician el 10 de julio.",
  "sources": [
    {
      "document": "Reglamento Académico.pdf",
      "page": 12
    }
  ],
  "audit_id": 1
}
```

---

# 3. Separar Conversaciones y Mensajes

## Problema

Actualmente conversación y chat están demasiado acoplados.

---

## Requisito

Separar recursos REST correctamente.

---

## Endpoints requeridos

### Conversaciones

```http
GET /api/conversations
POST /api/conversations
GET /api/conversations/{id}
DELETE /api/conversations/{id}
```

---

### Mensajes

```http
GET /api/conversations/{id}/messages
```

---

## Chat

```http
POST /api/chat/query
```

---

# 4. Mantener Contexto Administrativo Separado

## Requisito

Mantener prefijo:

```text
/api/admin/*
```

porque representa bounded context administrativo.

---

## Incluye

```text
/api/admin/documents
/api/admin/audit
/api/admin/reindex
/api/admin/users
/api/admin/metrics
```

---

# 5. Crear Endpoint Health Check

## Requisito

Implementar endpoint para monitoreo y deploy.

---

## Endpoint requerido

```http
GET /health
```

---

## Response

```json
{
  "status": "ok"
}
```

---

# 6. Crear Endpoint Readiness

## Requisito

Implementar endpoint de verificación de dependencias críticas.

---

## Endpoint requerido

```http
GET /ready
```

---

## Debe validar

* conexión Supabase
* conexión PostgreSQL
* disponibilidad OpenAI
* disponibilidad vector DB

---

## Response esperada

```json
{
  "status": "ready",
  "services": {
    "database": true,
    "openai": true,
    "vector_store": true
  }
}
```

---

# 7. Mantener Endpoint de Reindexación

## Requisito

Conservar endpoint:

```http
POST /api/admin/reindex
```

---

## Objetivo

Permitir:

* regeneración embeddings
* reindexación documentos
* reconstrucción vector store

---

# 8. Crear Endpoint de Métricas

## Requisito

Agregar endpoint administrativo para métricas del sistema.

---

## Endpoint requerido

```http
GET /api/admin/metrics
```

---

## Métricas iniciales sugeridas

* total consultas
* tiempo promedio respuesta
* cantidad conversaciones
* cantidad documentos indexados
* score promedio fidelidad
* score promedio relevancia

---

# 9. Crear Endpoint de Feedback

## Requisito

Agregar soporte de feedback del usuario.

---

## Endpoint requerido

```http
POST /api/chat/feedback
```

---

## Request esperado

```json
{
  "message_id": 1,
  "rating": 1,
  "comment": "La respuesta fue incorrecta"
}
```

---

## Objetivo

Permitir:

* mejora continua
* evaluación humana
* análisis calidad respuestas
* métricas UX

---

# 10. Mantener Sistema Mock Actual

## Requisito

NO integrar todavía:

* LangChain
* Whisper real
* embeddings reales
* OpenAI real
* Presidio
* pgvector real

---

## Objetivo

Primero estabilizar:

* contratos API
* arquitectura
* RBAC
* frontend integration
* schemas Pydantic
* persistencia mock

---

# 11. Prioridades Técnicas Inmediatas

## Orden recomendado

### 1.

Estabilizar schemas Pydantic

---

### 2.

Separar routers FastAPI correctamente

---

### 3.

Implementar auth mock limpio

---

### 4.

Conectar frontend React

---

### 5.

Persistir datos mock en Supabase

---

### 6.

Recién después integrar RAG real

---

# 12. Arquitectura Objetivo

```text
Frontend React
        │
        ▼
FastAPI Backend
 ├── Chat API
 ├── Voice API
 ├── Admin API
 ├── Audit API
 └── Metrics API
        │
        ▼
Supabase PostgreSQL + pgvector
```

---

# 13. Resultado Esperado de esta Fase

Al finalizar esta fase el backend debe tener:

✅ Arquitectura REST consistente
✅ Separación clara de dominios
✅ Contratos API definitivos
✅ Compatibilidad futura con RAG
✅ Compatibilidad futura con Whisper
✅ Compatibilidad futura con Presidio
✅ RBAC desacoplado de rutas
✅ Integración frontend lista
✅ Base sólida para IA real
