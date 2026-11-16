# Plan maestro de validación técnica y evidencia

**Estado al 2026-11-08.** Este documento separa el plan, los trabajos locales
realizados y las mediciones que siguen pendientes. Una prueba unitaria o un smoke
local no demuestra capacidad de producción.

## 1. Carga, latencia y concurrencia en entorno local sintético

### Objetivo

Validar el harness y observar latencia/concurrencia en una computadora local con
una institución sintética, sin producción ni una institución real. Esta corrida
no prueba capacidad de producción ni permite declarar cumplido el SLO de tesis.

### Procedimiento

1. Iniciar Supabase local con Colima/Docker, crear una institución y usuario de
   prueba sintéticos y cargar únicamente documentos/corpus sintéticos.
2. Iniciar FastAPI local en `127.0.0.1` y registrar versión, CPU/RAM, workers,
   modelos, flags, rate limit y estado efectivo del juez.
3. Ejecutar primero el perfil de 1 VU y después 8, 50 y 100 VUs, cada uno como
   corrida separada con al menos 100 solicitudes. Respetar pausas y límites de
   gasto configurados para los proveedores.
4. Repetir las corridas de diagnóstico con `judge_enabled` activado y desactivado
   (en evaluación, `judge_sample_rate=1.0`; en interactivo, `0.0`), manteniendo
   iguales el corpus, modelo, despliegue y demás flags.
5. Hacer perfiles con rate limit predeterminado y con un override local explícito.
   Mantenerlos separados; no extrapolar el override al comportamiento de producción.
6. Guardar el resumen de k6 y métricas del servidor por corrida. Clasificar 200,
   429, otros 4xx, 5xx y excepciones; calcular percentiles de latencia de éxito por
   separado de los errores.

### Criterios y evidencia

- Informar p50/p95/p99 de respuestas exitosas y número de respuestas por cálculo.
  Comparar P95 ≤ 3000 ms solo como referencia local, no como cumplimiento del SLO
  de producción.
- Tasa de error, códigos HTTP, CPU/RAM y RPS por escenario.
- Repetibilidad: configuración y fecha presentes en el reporte; no sobrescribir
  resultados históricos.
- **Estado:** ejecutado el harness local con Supabase, usuario e institución
  sintéticos. Se usó un esquema aislado (`eval/local_supabase_schema.sql`) para no
  modificar las migraciones del proyecto, que todavía fallan al intentar un
  bootstrap desde cero. Resultados y limitaciones:
  - 1 VU, 100 solicitudes: 100 % 200; P95 18,4 ms.
  - 8 VUs, 104 solicitudes: 100 % 200; P95 69,8 ms.
  - 50 VUs, 100 solicitudes: 100 % 200; P95 582,1 ms.
  - 100 VUs, 100 solicitudes: 100 % 200; P95 801,4 ms.
  - Con rate limit activo, 8 VUs y 104 solicitudes: 20 respuestas 200 y 84
    respuestas 429 (19,23 % de éxito).
  - Los escenarios son bursts de ~100 solicitudes, no carga sostenida. Usaron
    `LLM_ENABLED=false`, `EMBEDDINGS_ENABLED=false`, `JUDGE_ENABLED=false` y
    STT/TTS desactivados; por tanto, **no representan el pipeline con proveedores
    externos ni el SLO de 3 s**.
  - Carga sostenida local: 8 VUs, 240 solicitudes durante ~36 s; 240/240 respuestas
    200; P50 68,5 ms, P95 271,2 ms, máximo aislado 3,6 s; CPU `ps` promedio
    16,44 % (máximo 103,1 %) y RSS máximo 1.796,1 MB. Sigue siendo mock y no
    representa producción.
  - Evidencia: `eval/reports/local_validation_20261108.json`, exportaciones
    `eval/reports/k6_local_*`, reportes sostenidos `eval/reports/k6_sustained_*` y
    copia versionada en `docs/evidencias/2026-11-08/`.
- **Decisión:** mantener `eval/local_supabase_schema.sql` como fixture local aislado
  y no modificar las migraciones del proyecto en esta ronda. El esquema no es una
  migración de producción y debe revisarse si se necesita una réplica exacta.
- **Hecho después:** A/B real con 25 preguntas por condición y proveedores reales
  (ver sección 2). El bootstrap de migraciones sigue pendiente para pruebas de
  integración más fieles.

## 2. Calidad de respuestas y encuesta de validación

- Las métricas históricas de juez son resultados de un evaluador automático y no
  constituyen revisión humana ni precisión validada.
- Completar y revisar manualmente el Gold Dataset; generar la planilla ciega de
  `eval.run_eval`; hacer revisión de corrección, fidelidad a las fuentes y citas
  sustentadas. Si hay dos revisores, informar acuerdo entre evaluadores.
- No afirmar que la encuesta de validación se realizó si no hay instrumento,
  muestra, fechas y respuestas fuente disponibles. El valor histórico de usabilidad
  3,77/5 y 65 % favorable solo puede conservarse como dato previamente citado, no
  como evidencia verificada, hasta adjuntar su respaldo.
- **Ejecutado (automático):** RNF-05 definitiva con `openai/gpt-oss-20b` vía
  Groq y razonamiento low sobre 100 observaciones: P50 1.502 ms, P95 2.089 ms,
  0 errores; **cumple p95 ≤ 3 s en local**. A/B de juez (RF-52, histórico) con
  `openai/gpt-4o-mini`, embeddings `text-embedding-3-small`, corpus sintético
  indexado: juez OFF P50 2.176 ms / P95 3.936 ms; juez ON P50 4.189 ms / P95
  7.090 ms; fidelidad 0,996, relevancia 1,0, contexto 1,0. El juez añadió una
  mediana de +1.843 ms por consulta. Evidencia: `eval/reports/2026-11-08/`.
- **Estado:** sin revisión humana de respuestas ni evidencia de encuesta de
  validación en este repositorio. La planilla generada pero no completada no es un
  resultado de evaluación. Los scores del juez no se presentan como precisión humana.

## 3. Privacidad y falsos positivos PII

### Ajuste aplicado

`app/services/pii_service.py` aplica una excepción de span exacto y entidad
específica para el falso positivo español `Necesito` como `LOCATION` o `PERSON`.
No se elevó el umbral global de Presidio, y los analizadores locales para cédulas,
teléfonos, correos y self-PII no se filtran por esa regla.

### Verificación

- Prueba sintética local del 2026-11-08: 100 casos positivos y 20 controles
  negativos; 295/295 valores personales esperados anonimizados, 0 fugas,
  0 detecciones no esperadas y 0 controles negativos con detecciones.
- Reporte: `eval/reports/pii_20261108_170839_266425.json` (Python 3.12.16,
  spaCy `es_core_news_md` 3.8.0).
- Esta muestra sintética no prueba ausencia de falsos positivos/fugas en todas las
  poblaciones, idiomas, formatos o consultas reales. Ampliar corpus controlado y
  conservar pruebas de regresión antes de cualquier ajuste adicional.

## 4. Voz y WER en condiciones ordinarias

### Protocolo

1. Usar hasta 20 frases cortas del corpus sintético con transcripciones de
   referencia revisadas. Los audios TTS limpios son una prueba técnica del pipeline,
   no sustituyen una evaluación de voz humana.
2. Para una medición representativa, incorporar grabaciones de hablantes con
   consentimiento específico, micrófono/dispositivo habitual y ruido ambiente
   moderado (oficina/hogar); excluir deliberadamente ruido extremo, distancia
   anormal y condiciones adversas no previstas para el uso normal.
3. No incluir nombres, cédulas, correos ni datos reales. Mantener audio y referencias
   en un directorio único de evaluación con acceso restringido.
4. Reportar WER macro y de corpus, WER por muestra, latencia STT y latencia de voz
   extremo a extremo. Guardar modelos/configuración, condiciones y cantidad de
   muestras junto al resultado.
5. Las herramientas directas de WER/TTS requieren
   `EVAL_EXTERNAL_PROVIDERS_APPROVED=true`; esta bandera es una autorización
   operativa explícita para la corrida, no el consentimiento de los participantes.
   No ejecutar si falta autorización, presupuesto o credencial segura.

- **Estado:** WER completado sobre los 6 audios TTS existentes con
  `x-ai/grok-stt-1.0`: **macro 1,52 %** y **corpus 1,75 %** (1 error sobre 57
  palabras). El único error fue `ingresantes` → `ingresante` en g01. Es una
  muestra TTS pequeña; falta la evaluación con voz humana en condiciones normales.
  El generador sigue rechazando sobrescribir directorios no vacíos y ambas
  herramientas requieren `EVAL_EXTERNAL_PROVIDERS_APPROVED=true`.

## 5. Usabilidad y ahorro de tiempo

Sin cambios en esta ronda, según el alcance acordado. Cuando se retome, separar la
encuesta de usabilidad de la revisión de calidad de respuestas y medir ahorro de
tiempo con tareas equivalentes contra el proceso actual de atención.

## 6. Dependencias y variabilidad de proveedores

- LLM, juez, STT y TTS usan la ruta compatible con OpenAI configurada hacia
  OpenRouter (`OPENROUTER_BASE_URL`, credencial y modelos configurados). El modelo
  o proveedor upstream depende del identificador de modelo y de la disponibilidad
  de OpenRouter; no se debe afirmar que el upstream cambia automáticamente sin una
  política/configuración que lo demuestre.
- Embeddings usan actualmente `OpenAIEmbeddingsClient`, `OPENAI_API_KEY` y
  `embedding_model` directamente; no pasan por OpenRouter en la implementación
  actual.
- Cada resultado debe registrar fecha, gateway/ruta, identificadores de modelo y
  flags efectivos, nunca credenciales. Una variación de modelo o upstream puede
  cambiar calidad, latencia, precio y disponibilidad; repetir la evaluación tras
  cambios relevantes.
- **Estado:** documentado y observado. La generación actual usa
  `openai/gpt-oss-20b` vía Groq con razonamiento low; embeddings
  `text-embedding-3-small`; STT `x-ai/grok-stt-1.0` funcionó tras cargar créditos
  y completó el WER de 6 audios. El A/B histórico del juez usó
  `openai/gpt-4o-mini`. Una variación de modelo o proveedor puede cambiar
  calidad, latencia, precio y disponibilidad; repetir la evaluación tras cambios.

## Orden de ejecución

1. Resolver el bootstrap del esquema y preparar Supabase/API locales con datos
   sintéticos; verificar JWT de la instancia local.
2. Ejecutar carga k6 local y guardar reportes etiquetados explícitamente como
   `local`; no extrapolar al servidor de producción.
3. Ejecutar evaluación de voz solo tras autorizar las llamadas externas y preparar
   audios sin datos personales.
4. Mantener las evaluaciones humanas/encuesta como pendientes hasta disponer de
   muestras y formularios reales.
5. Actualizar `docs/EVIDENCIA_PRUEBAS.md` con resultados observados, sin reemplazar
   la evidencia histórica ni presentar tareas pendientes como exitosas.
