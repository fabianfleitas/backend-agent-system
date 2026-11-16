# Evaluación del asistente (Bloque 2, S12)

Material para validar el desempeño del sistema según los criterios del §5.1.3
de la tesis: fidelidad/relevancia (RAG + LLM-as-a-Judge), carga (RNF-03/04),
WER de voz (RF-07) y medición de CPU/RAM/uptime (RNF-05).

## Contenido

| Archivo | Propósito |
|---|---|
| `gold_dataset.json` | 50 consultas frecuentes (best-effort). Completar `respuesta_esperada`/`fuente_esperada` con la documentación institucional real. |
| `run_eval.py` | Ejecuta el Gold Dataset contra el pipeline y emite reporte en `reports/`. Un comando. |
| `enable_testing.sql` | Habilita los flags DB (`llm_enabled`, `judge_enabled` con `judge_sample_rate=1.0`, PII, handoff). Idempotente; restaurar `judge_sample_rate=0.0` al terminar. |
| `k6_load.js` | Burst de carga HTTP contra `/api/chat/query` (API local + JWT de usuario sintético; no requiere producción). |
| `k6_sustained.js` | Carga sostenida local con una conversación distinta por iteración y pausa configurable. |
| `run_sustained_local.py` | Ejecuta k6 sostenido y muestrea CPU/RSS del proceso backend sin imprimir el JWT. |
| `local_supabase_schema.sql` | Esquema aislado para una instancia Supabase local desechable; no es una migración de producción. |
| `seed_local_synthetic.py` | Crea usuario Auth, `app_users`, institución y membresía sintéticos; rechaza URLs que no sean localhost. |
| `load_local.py` | Línea base secuencial in-process con códigos HTTP y latencia exitosa; no simula concurrencia. |
| `uptime_check.py` | Probe de disponibilidad contra `/ready` (smoke local). |
| `pii_smoke.py` | 100 casos sintéticos positivos y 20 controles negativos; informa cobertura, fugas y detecciones no esperadas. No llama proveedores externos. |
| `gen_wer_audios.py` | Genera hasta 20 audios de referencia con TTS real en una carpeta única `audios/extended_<run>/`, sin sobrescribir los seis anteriores ni ejecuciones previas. |
| `wer.py` | WER del STT usando audios y referencias `.txt`; informa WER macro y de corpus. |
| `audios/` | Audios de prueba generados y sus referencias `.txt`. |
| `.env.example` | Variables de configuración de la evaluación. |

## Requisitos para evaluación local sintética

- Supabase local y backend local, con institución/usuario de prueba y documentos exclusivamente sintéticos indexados (`status=READY`). No se necesita producción ni una institución real.
- Flags habilitados:
- **DB** (`config_parametros`): `llm_enabled=true`; activar `judge_enabled` solo para la ejecución con juez. Registrar el valor efectivo para cada corrida.
  - **`.env` + reinicio**: `EMBEDDINGS_ENABLED=true` (retrieval); `STT_ENABLED=true` (WER); `TTS_ENABLED=true`.
- Para concurrencia local: k6 y backend HTTP en `127.0.0.1`; usar JWT del usuario sintético de Supabase local.
- Estas mediciones validan el harness y describen el rendimiento de esta computadora; no prueban capacidad de producción ni cumplen por sí mismas el SLO de despliegue.
- Registrar el rate limit por corrida; mantener separados los valores predeterminados y cualquier override local.

## Bootstrap local aislado

Las migraciones del repositorio no permiten crear actualmente un esquema desde
cero (la primera usa `CREATE TYPE IF NOT EXISTS`, no válido en PostgreSQL). Para
probar localmente sin modificar esas migraciones:

```bash
# 1) Instancia Supabase desechable (no usar un proyecto alojado)
mkdir -p /ruta/segura/voxia-local-supabase
cd /ruta/segura/voxia-local-supabase
supabase init
mv supabase/migrations supabase/migrations.disabled  # solo en esta copia temporal
supabase start

# 2) Crear el esquema local aislado desde la raíz del backend
docker exec -i supabase_db_<proyecto> psql -v ON_ERROR_STOP=1 \
  -U postgres -d postgres < eval/local_supabase_schema.sql

# 3) Claves y JWT solo en archivos locales con permisos restringidos
umask 077
supabase status -o env > .env.local
python -m eval.seed_local_synthetic \
  --env-file .env.local --jwt-file ./local_test.jwt

# 4) Iniciar backend con proveedores externos desactivados para la línea base
#    (exportar SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY desde .env.local;
#     no pegar las claves en la conversación ni en el historial del shell)
```

El esquema y el seed son herramientas de prueba. No se deben aplicar a una base
real ni usarse para reemplazar migraciones. El seed solo acepta
`http://127.0.0.1` o `http://localhost`.

## Ejecución (un comando, modo local)

```bash
# 1) Habilita flags DB (llm/judge/pii/handoff)
#    psql "$DATABASE_URL" -f eval/enable_testing.sql
# 2) .env: EMBEDDINGS_ENABLED=true  (+ STT/TTS si se prueba voz) y reinicia el backend
# 3) Evalúa con conversaciones aisladas por consulta y genera una planilla de revisión humana.
#    Requiere autorización explícita porque puede llamar LLM/embeddings/juez externos:
EVAL_EXTERNAL_PROVIDERS_APPROVED=true python3 -m eval.run_eval
```

Modo API real:

```bash
EVAL_API_URL=http://localhost:8000 EVAL_AUTH_TOKEN=<jwt> \
  EVAL_EXTERNAL_PROVIDERS_APPROVED=true python3 -m eval.run_eval
```

Variables: `EVAL_USER_ID`, `EVAL_INSTITUCION_ID` (modo local). Por defecto, el runner crea una conversación por consulta para evitar que el historial de una pregunta afecte la siguiente. `EVAL_CONVERSATION_ID` se usa solo si se acompaña de `EVAL_REUSE_CONVERSATION=true`.

Para comparar latencia con y sin juez, usar el mismo dataset, modelo, documentos y entorno, cambiar `judge_enabled` entre corridas y asignar etiquetas distintas. El reporte registra el estado resuelto del juez. Por ejemplo, tras configurar el parámetro institucional/global correspondiente:

```bash
EVAL_RUN_LABEL=judge-off-25 EVAL_LIMIT=25 EVAL_RATE_LIMIT_ENABLED=false \
  EVAL_EXTERNAL_PROVIDERS_APPROVED=true python3 -m eval.run_eval
# Cambiar sólo judge_enabled entre corridas. En evaluación se fuerza el
# muestreo al 100 % para obtener scores de todas las respuestas.
# El valor de BD tiene precedencia sobre JUDGE_SAMPLE_RATE del .env:
# subir config_parametros (global o de la institución de evaluación) a 1.0
# antes de la corrida y restaurarlo a 0.0 al terminar.
EVAL_RUN_LABEL=judge-on-25 EVAL_LIMIT=25 EVAL_RATE_LIMIT_ENABLED=false \
  EVAL_EXTERNAL_PROVIDERS_APPROVED=true python3 -m eval.run_eval
```

`judge_sample_rate` (en `config_parametros`) controla qué fracción de consultas
interactivas se evalúa cuando `judge_enabled=true`. El valor por defecto es `0.0`
para no añadir la llamada del juez a la ruta crítica (RNF-05); en corridas de
evaluación se usa `1.0`. Precedencia: institucional > global (BD) > `.env`.
Las respuestas no muestreadas quedan con la nota `JUDGE:skipped_sample` en la
auditoría. Si se edita por SQL, esperar ≤60 s (caché de `ConfigService`) o
reiniciar el backend.

```sql
-- Corrida A/B: subir el muestreo temporalmente y restaurarlo después
UPDATE config_parametros SET valor = '1.0', updated_at = now()
WHERE clave = 'judge_sample_rate' AND institucion_id IS NULL;
-- ... ejecutar la corrida ...
UPDATE config_parametros SET valor = '0.0', updated_at = now()
WHERE clave = 'judge_sample_rate' AND institucion_id IS NULL;
```

La primera corrida real de este repositorio usó **25 preguntas emparejadas**
(50 solicitudes de chat en total), no 50 por condición.

La diferencia de puntuaciones del juez no es una comparación válida de calidad entre modos si solo se evalúa la respuesta del modo “judge-on”. Para comparar calidad, someter las respuestas de ambos reportes a la misma revisión humana ciega o a un proceso evaluador independiente. La llamada del juez no modifica el texto de la respuesta.

Carga y WER:

```bash
# WER: estas acciones llaman TTS/STT externos y pueden tener costo.
# Activar solo después de aprobar el uso de proveedores y cargar credenciales de forma segura.
export EVAL_EXTERNAL_PROVIDERS_APPROVED=true
# Para reutilizar los 6 audios existentes, apuntar al directorio actual:
EVAL_WER_AUDIO_DIR='eval/audios' python3 -m eval.wer
# Para crear una tanda sintética nueva (TTS) y luego medirla:
python3 -m eval.gen_wer_audios
EVAL_WER_AUDIO_DIR='eval/audios/extended_20261108_120000_000000' python3 -m eval.wer

# Uptime (smoke local)
python3 -m eval.uptime_check

# Privacidad (motor local; no envía consultas a proveedores externos)
python3 -m eval.pii_smoke

# Línea base secuencial local; no es una prueba de VUs
EVAL_MAX_REQUESTS=100 EVAL_RATE_LIMIT_ENABLED=false python3 -m eval.load_local

# Carga HTTP local (requiere backend/Supabase locales y JWT sintético); 100+ solicitudes
export EVAL_API_URL='http://127.0.0.1:8000'
export EVAL_TOKEN="$LOCAL_TEST_JWT" # no usar JWT ni usuarios de producción
run="$(date +%Y%m%d_%H%M%S)"
for vus in 1 8 50 100; do
  EVAL_VUS=$vus EVAL_MIN_REQUESTS=100 k6 run \
    --summary-export "eval/reports/k6_${run}_${vus}vus.json" eval/k6_load.js
done

# Carga sostenida local + CPU/RSS del proceso backend (8 VUs, 240 solicitudes, ~36 s)
LOCAL_BACKEND_PID="$(pgrep -f 'uvicorn app.main:app.*--port 8001' | head -1)"
python -m eval.run_sustained_local \
  --token-file /ruta/segura/local_test.jwt \
  --backend-pid "$LOCAL_BACKEND_PID" \
  --vus 8 --iterations-per-vu 30 --sleep 1
```

## Resultados locales del harness (2026-11-08)

Medición sintética con `LLM_ENABLED=false`, `EMBEDDINGS_ENABLED=false`,
`JUDGE_ENABLED=false`, STT/TTS desactivados y rate limit desactivado:

| Escenario | Solicitudes | 200 | P50 | P95 |
|---|---:|---:|---:|---:|
| 1 VU | 100 | 100 | 17,2 ms | 18,4 ms |
| 8 VUs | 104 | 104 | 59,4 ms | 69,8 ms |
| 50 VUs | 100 | 100 | 389,5 ms | 582,1 ms |
| 100 VUs | 100 | 100 | 708,6 ms | 801,4 ms |

En la corrida separada con rate limit activo y 8 VUs: 20 respuestas 200 y 84
respuestas 429. El límite de 20 solicitudes/minuto por IP explica esos 429 en
esta configuración local.

Carga sostenida posterior: 8 VUs, 30 iteraciones por VU, pausa de 1 s, 240
solicitudes durante ~36 s, rate limit desactivado y respuestas mock. Resultado:
240/240 respuestas 200; P50 68,5 ms, P95 271,2 ms, promedio 192,9 ms y máximo
aislado 3,6 s; CPU `ps` promedio 16,44 %, máximo 103,1 %, y RSS máximo 1.796 MB.

Estos resultados no sustituyen una prueba del pipeline con proveedores externos ni
demuestran el SLO de 3 s. Evidencia agregada:
`eval/reports/local_validation_20261108.json`; exportaciones:
`eval/reports/k6_local_*vu.json` y `eval/reports/k6_sustained_*`; copia versionada:
`docs/evidencias/2026-11-08/`.

## RNF-05 — prueba definitiva (GPT-OSS-20B / Groq, 2026-11-08)

100 observaciones (2 × 50), Supabase local, corpus sintético, juez fuera,
`openai/gpt-oss-20b` vía OpenRouter con proveedor **Groq** forzado y razonamiento
low:

- P50 **1.502 ms**; P95 **2.089 ms**; máximo 5.735 ms.
- 100/100 respuestas 200; 0 errores; 100/100 fuentes esperadas.
- **RNF-05 se cumple** (p95 ≤ 3 s) en el entorno local.
- Evidencia: `eval/reports/2026-11-08/rnf05_local_20261108.md`,
  `rnf05_local_20261108_100obs.json`, `rnf05_local_384_4_A_20261108.json` y
  `rnf05_local_384_4_B_20261108.json`.

## A/B juez OFF/ON (RF-52, histórico)

Mismas 25 preguntas, corpus sintético indexado, Supabase local, LLM/juez
`openai/gpt-4o-mini` y embeddings `text-embedding-3-small`:

| Condición | Solicitudes | 200 | P50 | P95* | Máximo |
|---|---:|---:|---:|---:|---:|
| Juez OFF | 25 | 25 | 2.176 ms | 3.936 ms | 5.395 ms |
| Juez ON | 25 | 25 | 4.189 ms | 7.090 ms | 7.238 ms |

\* P95 sobre 25 observaciones: indicativo, no robusto para producción. El delta
pareado de latencia fue mediana +1.843 ms y promedio +1.922 ms. Juez ON obtuvo
fidelidad 0,996, relevancia 1,0 y contexto 1,0 sobre 25 respuestas; es evaluación
automática, no revisión humana. Reportes:
`eval/reports/eval_20261108_175752_280723.json`,
`eval/reports/eval_20261108_175956_080905.json` y
`eval/reports/ab_judge_20261108.json`.

WER: tras cargar créditos se completó sobre los 6 audios TTS existentes con
`x-ai/grok-stt-1.0`: **macro 1,52 %** y **corpus 1,75 %** (1 error sobre 57
palabras; `ingresantes` → `ingresante` en g01). Es una muestra TTS pequeña, no
voz humana en condiciones reales. Reporte:
`eval/reports/wer_20261108_181549_631213.json`.

## Resultados históricos de referencia (2026-09-22)

Estos valores corresponden a ejecuciones anteriores; no son resultados de las
modificaciones del harness. Conservarlos como evidencia histórica y generar reportes
nuevos, con fecha, configuración y entorno, para cada repetición.

- **RAG + Judge** (`run_eval.py`, 50 consultas): el reporte histórico anotó retrieval 45/50 y scores de juez fidelidad 0.99, relevancia 0.994 y contexto 0.986. Retrieval de fuente no equivale a respuesta correcta y las puntuaciones del juez no tuvieron revisión humana documentada; no presentarlas como calidad validada.
- **WER** (6 audios TTS→STT): promedio histórico **5.68 %**; muestra pequeña y sintética, no sustituye voz humana en condiciones normales.
- **Uptime** (smoke local, ventana 12 s): **100 %**.
- **Carga local anterior**: no utilizarla como evidencia de concurrencia. El harness
  antiguo compartía `TestClient` y conversación entre hilos, enviaba tareas sin límite
  a una cola y no separaba códigos HTTP ni latencias exitosas de fallidas. La concurrencia
  de este plan se medirá con k6 sobre HTTP en localhost y se etiquetará como evidencia
  exploratoria local; no extrapolarla a producción.

> Nota histórica: la latencia de ejecuciones con `judge_enabled=true` incluye una segunda llamada LLM en serie. No atribuir esa causa a una corrida concreta sin confirmar y registrar su configuración.

No se ha realizado revisión humana independiente de respuestas ni consta aquí una
encuesta formal de validación. La cifra de usabilidad 3,77/5 y 65 % favorable es un
dato previamente citado, pendiente de fuente primaria, instrumento y muestra; no
se considera verificado.

## Salida del reporte

`eval/reports/eval_<fecha>.json` incluye:
- `source_hit_rate`: coincidencia normalizada del título completo de la fuente esperada entre las fuentes recuperadas; **no mide corrección de respuesta**.
- `judge_scores` (`fidelidad_avg`, `relevancia_avg`, `contexto_avg`) leídos de `audit_logs` por `audit_id`.
- Por ítem: respuesta esperada y generada, fuentes, puntuaciones del juez, estado HTTP y latencia.
- Una planilla `human_review_<fecha>.csv` con campos de anotación vacíos para revisión humana.

Los promedios también se pueden contrastar con `/api/admin/metrics` (`avg_fidelity`, `avg_relevance`).

## Medición de rendimiento local y disponibilidad

La carga k6 descrita aquí es local. No requiere producción ni una institución
real, pero sus cifras describen solo la computadora donde corre. Para medir
producción se requeriría después un entorno desplegado representativo.

Criterios de referencia de la tesis:

- P95 de latencia ≤ 3 s; se informa por separado la latencia exitosa y los errores.
- Concurrencia en escenarios separados de 1, 8, 50 y 100 VUs, con un mínimo total de 100 solicitudes por escenario.
- Reportar 200, 429, otros 4xx, 5xx y excepciones; no atribuir causa sin revisar los códigos y registros.
- CPU < 70 %, RAM < 75 % (monitoreo del entorno de despliegue).
- Uptime ≥ 95 % mensual (registro de disponibilidad).
- Hasta 100.000 fragmentos vectorizados.

## Evaluación de voz sin condiciones extremas

El generador TTS produce audio sintético limpio y sirve solo para verificar el
pipeline. Para una evaluación representativa, usar hasta 20 frases sin PII, con
referencias revisadas y grabaciones de hablantes consentidas, capturadas con
dispositivos habituales y ruido ambiente moderado; no usar ruido extremo como
condición principal. Reportar WER macro/corpus, resultados por muestra y latencia.

Las herramientas `eval.gen_wer_audios` (TTS) y `eval.wer` (STT) ahora exigen la
bandera explícita `EVAL_EXTERNAL_PROVIDERS_APPROVED=true`; esta autorización de
ejecución no sustituye el consentimiento de personas grabadas. Cada corrida guarda
modelo y metadatos sin credenciales. No se realizaron llamadas de voz externas en
la actualización actual. El generador crea un directorio único por defecto y
rechaza sobrescribir un directorio de salida que ya contenga archivos.

## Proveedores actuales y variabilidad

- LLM, juez, STT y TTS usan OpenRouter como gateway compatible con OpenAI. El
  upstream/modelo depende de la configuración y disponibilidad vigentes; un cambio
  de ruta no debe asumirse automático ni invisible.
- Embeddings usan actualmente OpenAI directamente (`OPENAI_API_KEY` y
  `embedding_model`), no OpenRouter.
- Registrar para cada medición la fecha, gateway, modelo efectivo, flags y entorno;
  no registrar claves. Cambios de modelo/proveedor pueden alterar latencia, calidad,
  precio y disponibilidad.
- Plan consolidado: `docs/PLAN_VALIDACION_TECNICA.md`.
