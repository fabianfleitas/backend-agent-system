## Objetivo

Este documento resume los cambios pendientes en el frontend `student-module` para que la integracion con `backend-agent-system` funcione correctamente y de forma estable.

Se basa en el analisis del proyecto frontend ubicado en:

```text
/Users/ServiciosDigitales/Documents/fabian/projects/student-module
```

Y en el contrato backend vigente documentado en:

```text
FRONTEND_API_INTEGRATION.md
```

Este documento no describe el contrato HTTP. Describe el trabajo concreto que todavia debe hacerse en el frontend.

## Estado actual del frontend

Stack detectado:

- React 19
- TypeScript
- Vite
- Zustand

Archivos principales analizados:

- `src/services/api.ts`
- `src/services/chat.service.ts`
- `src/store/chat.store.ts`
- `src/modules/chat/ChatPage.tsx`
- `src/context/UserContext.tsx`
- `src/types/index.ts`
- `FRONTEND_API_INTEGRATION.md`
- `BACKEND_HANDOFF.md`

Capacidades ya presentes:

- Cliente HTTP con headers delegados.
- Flujo para crear conversacion.
- Flujo para chat por texto.
- Flujo para chat por voz con `multipart/form-data`.
- Carga de historial.
- Store global de chat.
- Contexto de alumno desde portal embebido.

## Resumen ejecutivo

El frontend ya esta bastante cerca de una integracion funcional, pero todavia tiene pendientes en cuatro frentes:

1. Consumir como contrato principal la nueva respuesta de `chat/query` y `chat/voice`.
2. Reconciliar mejor el store local con el historial persistido para evitar duplicados y estados inconsistentes.
3. Cerrar UX operativas que hoy estan incompletas: retomar historial, ocultar conversaciones y enviar feedback.
4. Endurecer validaciones y manejo de errores para contexto de alumno, audio y respuestas parciales.

## Prioridad 1: Alinear el servicio de chat con el contrato real

### Problema

El frontend ya tolera respuestas del backend con varios formatos antiguos y de transicion, pero ahora el backend devuelve un contrato mas estable con:

- `conversation_id`
- `user_message`
- `assistant_message`
- `sources`
- `audit_id`

El frontend todavia mantiene varios fallbacks heredados que complican el flujo y hacen mas dificil depurar.

### Archivos a cambiar

- `src/services/chat.service.ts`
- `src/types/index.ts`

### Cambios requeridos

- Priorizar como contrato principal:
  - `response`
  - `conversation_id`
  - `user_message`
  - `assistant_message`
  - `sources`
  - `audit_id`
- Mantener fallbacks viejos solo si se necesita compatibilidad temporal y documentarlo explicitamente.
- Reducir dependencia de campos alternativos como:
  - `answer`
  - `rag_documents`
  - `conversation?.id`
- Usar `user_message` y `assistant_message` como fuente principal para:
  - `userMessageId`
  - `assistantMessageId`
  - `createdAt`
  - `question`
  - `answer`
  - `auditId`

### Criterio de aceptacion

- Enviar una consulta de texto actualiza el store sin tener que refrescar inmediatamente el detalle de conversacion.
- Enviar una consulta de voz actualiza el store con el mismo criterio.
- El frontend no depende de estructuras legacy para renderizar el ultimo intercambio.

## Prioridad 2: Reconciliar historial y store sin duplicados

### Problema

El store inserta un mensaje visual local al responder una consulta, pero el historial tambien se reconstruye desde backend. Sin reconciliacion explicita puede haber:

- duplicados
- orden incorrecto
- mensajes de error mezclados con mensajes persistidos
- reintentos que duplican entradas visibles

### Archivos a cambiar

- `src/store/chat.store.ts`
- `src/services/chat.service.ts`
- `src/types/index.ts`

### Cambios requeridos

- Definir una estrategia clara de identidad de mensaje para UI.
- Dejar de depender solo de `crypto.randomUUID()` como identificador visual final cuando ya existen:
  - `conversationId`
  - `userMessageId`
  - `assistantMessageId`
- Al cargar historial desde backend:
  - reconciliar mensajes existentes
  - evitar insertar duplicados del mismo par `USER` + `ASSISTANT`
- Al reintentar una consulta:
  - reemplazar o marcar el mensaje fallido anterior
  - no apilar mensajes equivalentes indefinidamente
- Separar claramente:
  - mensaje pendiente
  - mensaje exitoso persistido
  - mensaje fallido

### Criterio de aceptacion

- Si el usuario envia una consulta y luego refresca historial, no aparecen duplicados.
- Si el usuario reintenta una consulta fallida, la UI no genera varias copias incoherentes.
- El orden cronologico es estable en historial y vista principal.

## Prioridad 3: Permitir retomar conversaciones historicas

### Problema

La UI muestra historial, pero hoy no queda cerrado el flujo para seleccionar una conversacion previa y convertirla en la conversacion activa del chat.

### Archivos a cambiar

- `src/modules/history/HistoryPage.tsx`
- `src/modules/chat/ChatPage.tsx`
- `src/store/chat.store.ts`
- `src/types/index.ts`

### Cambios requeridos

- Agregar accion de seleccionar una conversacion o mensaje historico.
- Al seleccionar historial:
  - establecer `activeConversationId`
  - poblar la vista principal con los mensajes de esa conversacion
  - cerrar el panel de historial si aplica
- Definir si el usuario:
  - continua la conversacion existente
  - o solo visualiza historial y siempre inicia una nueva

Recomendacion:

- Permitir continuar la conversacion historica si el backend ya soporta ownership y persistencia por `conversation_id`.

### Criterio de aceptacion

- El alumno puede abrir un item del historial y seguir preguntando dentro de esa misma conversacion.
- Las nuevas respuestas quedan asociadas al `conversation_id` correcto.

## Prioridad 4: Implementar ocultar conversacion

### Problema

El backend ya soporta:

```text
DELETE /api/conversations/{conversation_id}
```

pero el frontend todavia no tiene una UX cerrada para ocultar conversaciones.

### Archivos a cambiar

- `src/services/chat.service.ts`
- `src/store/chat.store.ts`
- `src/modules/history/HistoryPage.tsx`

### Cambios requeridos

- Agregar servicio para ocultar conversacion.
- Agregar accion en historial.
- Al ocultar:
  - actualizar el store local
  - sacar la conversacion de la lista visible
  - si era la conversacion activa, decidir si:
    - se limpia el chat
    - o se crea una nueva conversacion al siguiente envio

### Criterio de aceptacion

- El usuario puede ocultar una conversacion desde el historial.
- La conversacion deja de aparecer en `include_hidden=false`.
- No se interpreta visualmente como borrado permanente.

## Prioridad 5: Implementar feedback del alumno

### Problema

El backend ya soporta `POST /api/chat/feedback`, pero el frontend todavia no parece tener un flujo completo para enviar valoracion de respuestas.

### Archivos a cambiar

- `src/services/chat.service.ts`
- `src/store/chat.store.ts`
- `src/modules/chat/ChatResponse.tsx`
- `src/types/index.ts`

### Cambios requeridos

- Agregar accion visible para enviar feedback sobre un mensaje del asistente.
- Usar:
  - `assistantMessageId`
  - `auditId`
- Definir UX minima:
  - rating 1..5
  - comentario opcional
  - estado enviado / error

### Criterio de aceptacion

- Cada respuesta del asistente con `auditId` puede recibir feedback.
- Si el mensaje no es valido para feedback, la UI no ofrece la accion o la deshabilita.

## Prioridad 6: Manejo claro del contexto del alumno

### Problema

El frontend depende de contexto delegado del portal. Si ese contexto no llega o llega incompleto, la falla final aparece como error de backend o de fetch, no como problema de sesion embebida.

### Archivos a cambiar

- `src/context/UserContext.tsx`
- `src/hooks/useUser.ts`
- `src/services/api.ts`
- `src/app/App.tsx`

### Cambios requeridos

- Validar que exista `studentId` antes de cualquier llamada al backend.
- Mostrar error claro si falta contexto embebido.
- Definir comportamiento en desarrollo:
  - fallback permitido
  - fallback prohibido en produccion
- Normalizar vocabulario de rol:
  - front usa `ALUMNO`
  - backend usa `ESTUDIANTE` en header y `STUDENT` en respuesta

Recomendacion:

- Mantener `ALUMNO` solo para UI si se necesita, pero mapear internamente a un tipo de sesion mas estable.

### Criterio de aceptacion

- Si falta contexto del portal, la UI muestra un error entendible.
- El frontend nunca hace llamadas sin `X-External-Auth-Id`.

## Prioridad 7: Mejorar manejo de audio

### Problema

El flujo de voz existe, pero falta robustez de UX y validacion.

### Archivos a cambiar

- `src/modules/chat/ChatInput.tsx`
- `src/services/chat.service.ts`
- `src/store/chat.store.ts`
- `src/types/index.ts`

### Cambios requeridos

- Validar antes de enviar:
  - tipo MIME
  - tamaño maximo
  - existencia real de `blob` u `objectUrl`
- Mostrar estados de voz mas claros:
  - preparando audio
  - enviando
  - transcribiendo
  - error
- No asumir que `ruta_audio_respuesta` es reproducible por URL.
- Si el backend sigue con TTS mock:
  - renderizar respuesta textual
  - no mostrar controles de reproduccion falsos

### Criterio de aceptacion

- Un error al preparar audio no rompe el store.
- El usuario entiende si la respuesta de voz es solo textual por ahora.

## Prioridad 8: Optimizar carga de historial

### Problema

Hoy el frontend lista conversaciones y luego pide detalle de cada una. Eso es aceptable al inicio, pero escala mal.

### Archivos a cambiar

- `src/services/chat.service.ts`
- `src/store/chat.store.ts`

### Cambios requeridos

- Mantener el enfoque actual como primera etapa si el volumen es bajo.
- Agregar manejo de:
  - loading parcial
  - error parcial
  - conversaciones sin detalle cargado todavia
- Evaluar mas adelante si conviene:
  - un endpoint resumido con ultimo intercambio
  - lazy loading del detalle al abrir historial

### Criterio de aceptacion

- El historial no bloquea toda la UI si falla una conversacion puntual.
- La carga inicial sigue siendo usable con varias conversaciones.

## Prioridad 9: Ajustar tipado frontend

### Problema

Los tipos actuales mezclan entidad de backend, estado local y modelo visual.

### Archivos a cambiar

- `src/types/index.ts`

### Cambios requeridos

- Separar tipos de:
  - transporte HTTP
  - store interno
  - componente visual
- Definir tipos concretos para:
  - `BackendMessage`
  - `BackendChatResponse`
  - `ConversationSummary`
  - `ConversationDetail`
  - `ChatMessage`
  - `FeedbackPayload`

### Criterio de aceptacion

- El servicio de API no necesita tipos ambiguos o sobrecargados.
- Los componentes renderizan tipos preparados para UI, no payloads crudos del backend.

## Prioridad 10: Pruebas manuales minimas

### Objetivo

Antes de considerar terminada la integracion del modulo de estudiante, ejecutar esta secuencia:

1. Cargar el modulo con contexto de alumno valido.
2. Crear una conversacion nueva.
3. Enviar un mensaje de texto.
4. Ver respuesta inmediata del asistente.
5. Refrescar el historial.
6. Reabrir esa conversacion.
7. Enviar un mensaje de voz.
8. Ver `sources` si existen.
9. Enviar feedback sobre la respuesta.
10. Ocultar la conversacion.

### Resultado esperado

- No hay duplicados en historial.
- La conversacion activa se mantiene correctamente.
- La persistencia en backend refleja texto, voz, feedback e historial.
- Las acciones fallidas muestran errores claros y no dejan el store corrupto.

## Orden recomendado de implementacion

Orden sugerido para el equipo frontend:

1. Alinear `chat.service.ts` con el contrato real.
2. Reconciliar el store e identidad de mensajes.
3. Habilitar retomar conversacion historica.
4. Implementar ocultar conversacion.
5. Implementar feedback.
6. Mejorar validaciones de contexto y audio.
7. Optimizar historial y tipado.

## Dependencias con backend

Estos puntos ya estan disponibles o encaminados en backend:

- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `DELETE /api/conversations/{conversation_id}`
- `POST /api/chat/query`
- `POST /api/chat/voice`
- `POST /api/chat/feedback`
- `conversation_id`, `user_message` y `assistant_message` en respuestas de chat
- `audit_id` para feedback

Puntos que siguen siendo limitaciones reales del backend y que el frontend debe contemplar:

- La respuesta IA sigue siendo mock.
- La transcripcion de voz sigue siendo mock.
- TTS real no existe todavia.
- `sources` todavia son mock.
- No existe endpoint publico para descargar audio desde rutas de storage.

## Checklist final

- Consumir `conversation_id`, `user_message` y `assistant_message` como contrato principal.
- Evitar duplicados entre respuesta inmediata e historial persistido.
- Permitir retomar conversaciones historicas.
- Implementar ocultar conversacion.
- Implementar feedback con `assistantMessageId` y `auditId`.
- Validar contexto del alumno antes de llamar al backend.
- Mejorar estados de UI para audio.
- No tratar rutas de audio como URLs publicas.
- Separar tipos de backend y tipos de UI.
- Ejecutar la prueba manual completa del modulo.
