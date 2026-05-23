# Backend – Sistema de Asistente Académico Inteligente
## Documento de análisis funcional y técnico
### Stack principal: FastAPI + Python + RAG + Voz

---

# 1. Descripción general

## 1.1 Propósito del backend

El backend será el núcleo central del sistema de asistencia académica inteligente para estudiantes universitarios.

El sistema permitirá:

- Procesar consultas académicas basadas estrictamente en reglamentos y documentos institucionales
- Integrar procesamiento de voz
- Gestionar historial permanente de consultas
- Implementar arquitectura RAG desde el inicio
- Administrar documentos académicos institucionales
- Integrarse con modelos IA mediante OpenRouter
- Proveer APIs desacopladas para frontend estudiantil y panel administrativo

---

# 2. Objetivos del sistema

## Objetivo general

Desarrollar una plataforma backend modular y escalable capaz de responder consultas académicas institucionales utilizando procesamiento de lenguaje natural y recuperación contextual de documentos.

---

## Objetivos específicos

- Implementar arquitectura RAG desde el inicio
- Procesar consultas por texto y voz
- Garantizar aislamiento de información entre estudiantes
- Gestionar reglamentos institucionales versionados
- Mantener historial permanente de conversaciones
- Permitir futura evolución a tiempo real (WebRTC)
- Integrarse con proveedores IA externos mediante OpenRouter
- Registrar auditoría y trazabilidad de interacciones

---

# 3. Alcance funcional

El backend incluirá:

- API REST FastAPI
- Integración RAG
- Procesamiento Speech-to-Text
- Procesamiento Text-to-Speech
- Gestión de documentos PDF
- Historial de consultas
- Persistencia de audios
- Administración documental
- Versionado de documentos
- Validación de identidad delegada
- Soporte multiusuario concurrente

---

# 4. Arquitectura general

```plaintext
Frontend Alumno
        ↓
(API REST)
        ↓

┌────────────────────────────────────┐
│            FastAPI Core            │
│                                    │
│ - Student API                      │
│ - Voice API                        │
│ - Auth Delegada                    │
│ - Historial                        │
│ - Gestión RAG                      │
│ - Administración documentos        │
│ - Auditoría                        │
└────────────────────────────────────┘
                ↓

 ┌────────────┬──────────────┬──────────────┬──────────────┐
 │            │              │              │              │
PostgreSQL  Vector DB     OpenRouter      Whisper/TTS   File Storage
            (pgvector)       LLM             Voz          Audios/PDF

```
---
# 5. Flujo RAG

```plaintext
Pregunta estudiante
        ↓
Embeddings consulta
        ↓
Búsqueda semántica
        ↓
Recuperación fragmentos reglamento
        ↓
Construcción prompt contextual
        ↓
OpenRouter / LLM
        ↓
Respuesta institucional

```

# 6. Arquitectura sugerida

```plaintext
backend/
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── database.py
│   │   └── logging.py
│   │
│   ├── api/
│   │   ├── student/
│   │   ├── admin/
│   │   └── voice/
│   │
│   ├── services/
│   │   ├── ai/
│   │   ├── rag/
│   │   ├── voice/
│   │   ├── embeddings/
│   │   ├── history/
│   │   └── documents/
│   │
│   ├── repositories/
│   ├── models/
│   ├── schemas/
│   ├── middleware/
│   ├── integrations/
│   ├── workers/
│   └── utils/
│
├── storage/
│   ├── audio/
│   └── documents/
│
├── tests/
│
├── requirements.txt
└── alembic/

```

Arquitectura sugerida
| Componente              | Tecnología                 |
| ----------------------- | -------------------------- |
| Backend                 | FastAPI                    |
| Lenguaje                | Python                     |
| ORM                     | SQLAlchemy                 |
| Validación              | Pydantic                   |
| Migraciones             | Alembic                    |
| Base de datos           | PostgreSQL                 |
| Vector Search           | pgvector                   |
| IA                      | OpenRouter                 |
| Embeddings              | OpenAI Embeddings (?)      |
| Speech-to-Text          | OpenRouter o Whisper       |
| Text-to-Speech          | OpenRouter u OpenAI TTS                 |
| Procesamiento asíncrono | Celery                     |
| Broker                  | Redis                      |
| Testing                 | Pytest                     |
| File Storage            | Sistema local inicialmente |


