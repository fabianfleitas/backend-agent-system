# 1. Requisitos funcionales
RF-01 – Consultas académicas

El sistema debe permitir recibir consultas académicas de estudiantes autenticados.

Las consultas deben responder exclusivamente utilizando información institucional.

RF-02 – Arquitectura RAG

El sistema debe implementar Retrieval-Augmented Generation desde el inicio.

Debe:

indexar documentos institucionales
generar embeddings
recuperar contexto relevante
construir prompts contextualizados

RF-03 – Restricción de dominio institucional

El sistema debe limitar respuestas únicamente a reglamentos y documentos institucionales.

No debe responder preguntas fuera del alcance académico institucional.

RF-04 – Procesamiento de voz

El sistema debe:

recibir audios grabados
almacenar audios
transcribir voz a texto
generar respuesta IA
sintetizar respuesta en audio

RF-05 – Persistencia de audio

El sistema debe almacenar:

archivos de audio originales
transcripciones
duración de grabación
metadata asociada
RF-06 – Historial permanente

El sistema debe almacenar historial permanente de interacciones.

Debe permitir:

recuperación histórica
filtrado por estudiante
ocultamiento visual para el usuario

El ocultamiento NO debe eliminar físicamente registros.

RF-07 – Gestión documental

El sistema debe permitir:

carga de PDFs
versionado documental
actualización de reglamentos
reindexación RAG

RF-08 – Versionado documental

El sistema debe mantener versiones históricas de documentos institucionales.

Debe permitir:

identificar documento activo
conservar historial de cambios
evitar pérdida documental
RF-09 – Autenticación delegada

El sistema debe operar bajo autenticación delegada simulada.

Debe:

validar identidad recibida
derivar studentId desde contexto seguro
impedir acceso cruzado entre alumnos

RF-10 – Integración OpenRouter

El sistema debe estar preparado para integrarse con OpenRouter como gateway de modelos IA.

Debe permitir:

cambiar modelos
cambiar proveedores
controlar costos
manejar fallos externos

RF-11 – Procesamiento asíncrono

El sistema debe soportar procesamiento asíncrono para:

embeddings
indexación
procesamiento de voz
tareas pesadas

RF-12 – Administración académica

El sistema debe permitir a administradores:

cargar documentos
visualizar auditoría
gestionar reglamentos
monitorear consultas

RF-13 – Concurrencia multiusuario

El sistema debe soportar múltiples estudiantes concurrentes.

Debe garantizar:

aislamiento de contexto
separación de conversaciones
seguridad de acceso

RF-14 – APIs REST

El sistema debe exponer APIs RESTful para:

consultas
voz
historial
administración
documentos

9. Requisitos no funcionales

RNF-01 – Rendimiento

Las respuestas textuales deben generarse idealmente en menos de 5 segundos.

RNF-02 – Escalabilidad

RNF-03 – Seguridad

El sistema debe:

evitar acceso entre alumnos
validar identidad delegada
proteger endpoints administrativos
impedir exposición de reglamentos internos

RNF-04 – Modularidad

Los módulos:

RAG
voz
IA
historial
documentos

Deben mantenerse desacoplados.

RNF-05 – Tolerancia a fallos

El sistema debe manejar:

errores de OpenRouter
errores STT/TTS
caídas parciales
timeouts externos
RNF-06 – Persistencia

El sistema debe conservar:

historial
audios
documentos
embeddings
auditoría

RNF-07 – Observabilidad

El sistema debe registrar:

logs
errores
duración consultas
métricas IA
uso de tokens

RNF-08 – Compatibilidad

El backend debe soportar:

JSON
multipart/form-data
futuros WebSockets/WebRTC
RNF-09 – Mantenibilidad

El sistema debe seguir arquitectura desacoplada y modular.

Debe permitir:

testing independiente
reemplazo de proveedores IA
evolución incremental
RNF-10 – Preparación para tiempo real

Aunque inicialmente el sistema funcionará mediante requests HTTP tradicionales, la arquitectura debe prepararse para futura migración a WebRTC streaming.

10. Modelo de datos inicial

11. Flujo de voz propuesto
Alumno habla
        ↓
Frontend graba audio
        ↓
multipart/form-data
        ↓
Backend FastAPI
        ↓
Whisper (STT)
        ↓
RAG + OpenRouter
        ↓
Respuesta textual
        ↓
TTS
        ↓
Audio respuesta
12. Límite recomendado de audio

Se recomienda:

duración máxima: 30 segundos
tamaño máximo configurable
rechazo automático de audios excesivos

13. Procesamiento asíncrono

Se recomienda utilizar Celery + Redis para:

generación embeddings
indexación PDFs
procesamiento documentos
tareas de voz pesadas

16. Endpoints iniciales sugeridos
Student API
Método	Endpoint	Descripción
POST	/api/student/query	Consulta textual
POST	/api/student/voice-query	Consulta voz
GET	/api/student/history	Historial
PATCH	/api/student/history/{id}/hide	Ocultar conversación
Admin API
Método	Endpoint	Descripción
POST	/api/admin/documents	Cargar PDF
GET	/api/admin/documents	Listar documentos
POST	/api/admin/reindex	Reindexar embeddings
GET	/api/admin/audit	Auditoría


