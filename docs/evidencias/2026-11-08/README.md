# Evidencia local — 2026-11-08

Copia de los reportes generados en la estación local con Supabase y datos
sintéticos. **No son resultados de producción ni de una institución real.**

## Contenido

| Archivo | Contenido |
|---|---|
| `local_validation_20261108.json` | Resumen agregado de las corridas k6 locales. |
| `k6_local_1vu.json` | Burst de 100 solicitudes, 1 VU, sin rate limit. |
| `k6_local_8vu.json` | Burst de 104 solicitudes, 8 VUs, sin rate limit. |
| `k6_local_50vu.json` | Burst de 100 solicitudes, 50 VUs, sin rate limit. |
| `k6_local_100vu.json` | Burst de 100 solicitudes, 100 VUs, sin rate limit. |
| `k6_local_8vu_rate_limit.json` | Resumen con rate limit activo: 20 × 200 y 84 × 429. |
| `k6_local_8vu_rate_limit_raw.json` | Puntos crudos de k6 para verificar los códigos anteriores. |
| `k6_sustained_20261108_173901_391454.json` | Resumen k6 de carga sostenida: 8 VUs, 240 solicitudes, ~36 s. |
| `k6_sustained_20261108_173901_391454_result.json` | Contexto y muestras CPU/RSS del backend durante la carga sostenida. |
| `eval_20261108_175752_280723.json` | A/B real, 25 preguntas con juez OFF. |
| `eval_20261108_175956_080905.json` | A/B real, las mismas 25 preguntas con juez ON. |
| `ab_judge_20261108.json` | Comparación consolidada de latencia, tokens y scores del A/B. |
| `human_review_20261108_175752_281870.csv` | Planilla humana del pase OFF, vacía. |
| `human_review_20261108_175956_082241.csv` | Planilla humana del pase ON, vacía. |
| `rnf05_local_20261108.md` | Resumen de la prueba definitiva RNF-05 (GPT-OSS-20B / Groq). |
| `rnf05_local_20261108_100obs.json` | Resumen agregado de las 100 observaciones RNF-05. |
| `rnf05_local_384_4_A_20261108.json` | Corrida A RNF-05 (50 consultas). |
| `rnf05_local_384_4_B_20261108.json` | Corrida B RNF-05 (50 consultas). |
| `historicos/wer_attempt_20261108.json` | Intento inicial de WER bloqueado por HTTP 402; archivado como antecedente. |
| `wer_20261108_181549_631213.json` | WER completado sobre los 6 audios: macro 1,52 %, corpus 1,75 %. |
| `pii_20261108_170839_266425.json` | Smoke PII: 120/120 casos, 295/295 valores protegidos, 0 fugas. |

La carga sostenida usó respuestas mock, `RATE_LIMIT_ENABLED=false` y pausas de
1 s: 100 % de respuestas 200, P95 271 ms y un máximo aislado de 3,6 s. No es una
medición sostenida con LLM/RAG ni de producción.

## A/B real juez OFF/ON

Mismas 25 preguntas del Gold Dataset, corpus sintético indexado con
`text-embedding-3-small`, LLM y juez `openai/gpt-4o-mini`, en local:

- Juez OFF: 25/25 respuestas 200; P50 2.176 ms, P95 3.936 ms, máximo 5.395 ms.
- Juez ON: 25/25 respuestas 200; P50 4.189 ms, P95 7.090 ms, máximo 7.238 ms.
- Delta pareado de latencia: mediana +1.843 ms, promedio +1.922 ms.
- Juez ON: 25 evaluaciones; fidelidad 0,996, relevancia 1,0, contexto 1,0.
- Tokens LLM: 18.956 de entrada y ~1.580 de salida por condición; el juez añade
  llamadas no incluidas en esos tokens del mensaje.
- Las 25 fuentes esperadas aparecieron en las respuestas recuperadas en ambas
  condiciones. Esto no mide corrección humana.

## RNF-05 — prueba definitiva (GPT-OSS-20B / Groq)

Configuración adoptada: `openai/gpt-oss-20b` vía OpenRouter, proveedor **Groq**
forzado (`allow_fallbacks=false`), razonamiento **low**,
`llm_max_tokens=384`, `retrieval_match_count=4`, juez fuera. Entorno local,
Supabase local y corpus sintético; 100 observaciones (2 × 50):

- P50 **1.502 ms**; P95 **2.089 ms**; máximo 5.735 ms.
- 100/100 respuestas 200; 0 errores; 100/100 fuentes esperadas.
- **RNF-05 se cumple en esta corrida local** (P95 ≤ 3 s).
- Evidencia: `rnf05_local_20261108.md`, `rnf05_local_20261108_100obs.json`,
  `rnf05_local_384_4_A_20261108.json` y `rnf05_local_384_4_B_20261108.json`.

## WER completado

Tras cargar créditos se ejecutó el WER con los 6 audios existentes y el modelo
`x-ai/grok-stt-1.0`:

- **WER macro: 1,52 %**; **WER corpus: 1,75 %**.
- Distancia total: 1 palabra sobre 57 palabras de referencia.
- g01: 9,09 % (`ingresantes` → `ingresante`); g02–g06: 0 %.
- Reporte: `wer_20261108_181549_631213.json`.

Es una muestra TTS pequeña y no sustituye una evaluación con voz humana en
condiciones normales. El intento anterior bloqueado por HTTP 402 se conserva en
`historicos/wer_attempt_20261108.json` como antecedente.

## Configuración

- RNF-05 (definitiva): `openai/gpt-oss-20b` vía OpenRouter/Groq, reasoning low,
  Supabase local, embeddings `text-embedding-3-small`.
- A/B de juez (RF-52, histórica): `openai/gpt-4o-mini`; no es la configuración
  actual de generación.
- WER: `x-ai/grok-stt-1.0`.
- Carga k6: `LLM_ENABLED=false`, `EMBEDDINGS_ENABLED=false`,
  `JUDGE_ENABLED=false`, `STT_ENABLED=false`, `TTS_ENABLED=false`.
- Las respuestas de la carga fueron mock; los escenarios son bursts de
  aproximadamente 100 solicitudes. El A/B y RNF-05 usaron proveedores reales.

## Integridad

Hashes SHA-256:

```text
1f208c05004114ec8506674e0357b0493b2c223bcdd8cc47426ef7862e4997fc  k6_local_100vu.json
d61f612dc68b2a1799d81db8976ec1ea674a321a3776775580f7abcf108f02fa  k6_local_1vu.json
f3577270084398ada1dd24ac74611d72b03a7144725fbe45903286dde7cdbdcd  k6_local_50vu.json
95367f3fbf35b308fc4904404b5390086b861f49da09ab778ebd6ca2a2217ad2  k6_local_8vu.json
6b105d0b17a795b492ea29ca5c18a47b7e637be80edb71fbfc93e75b60281fb6  k6_local_8vu_rate_limit.json
2e114a2a636e64cf6ffd7d7e893e99aa5968d8217fd3bd89b89f66d9726dfb19  k6_local_8vu_rate_limit_raw.json
df6cf8067c6a8236801f7a752c21392383d8c4c121ee2f768ba6e999a9d556f8  local_validation_20261108.json (versión inicial)
beeb3740aedc3c766932cd27deb8319163ae473023ad0188152ac6b2e23e1fef  local_validation_20261108.json (con carga sostenida)
a56260a6364897ca06a1ba3a4e71543d57288e20447bc797d0a9a5e85d977162  pii_20261108_170839_266425.json
2b69b15a5648aad3f20f4693b394d2e918a971cb16752a3ece9d4bd07b5f6145  k6_sustained_20261108_173901_391454.json
2c34d24bdfdca08fd0e104552ee88a59e930eb7da78af96b7aba2464cf491b23  k6_sustained_20261108_173901_391454_result.json
c2f46dacc842bfb3ffe88faa21bc49b00d873e5c127479b70c400eaf354c47df  eval_20261108_175752_280723.json
3228431ce2f6e96eb81483ae062c2539eab148fe6118333cf2d6e0a3e3803bad  eval_20261108_175956_080905.json
762c74bdb06932441d03d20ae4869bc7e89989ecaca86f71642cd22b9c147b6f  ab_judge_20261108.json
12a9667a1877f87e2ef6e8703986d40334e7db547c5cd6d1ce1935078846ec62  human_review_20261108_175752_281870.csv
8f729acd6b7a5e45d61f55d863d9b3221b87d10e8bca53b7e8278caa29ea27eb  human_review_20261108_175956_082241.csv
224ecdbbbdc6aa779e76124afe6833670483c65c2fd3cba77825e0cf32e3fbd4  historicos/wer_attempt_20261108.json
534266330042f02d5c4c100370f4f3f7f5fbc0b8aee4c394e69f560e10f82b69  wer_20261108_181549_631213.json
bf2c1b8a788615aee2c4a75c93a860b8dd9a8a15c393b72315fc879cb39ad46a  rnf05_local_20261108.md
6ad3a7ad6e8b0531f125268c11b002f6f1f740e506160676b6dc0f1773d8f880  rnf05_local_20261108_100obs.json
22f9b2f798b4b8739ac016688efafefa8830605e486bd22ef70243bf0b1383ae  rnf05_local_384_4_A_20261108.json
768cbe1248b19c6ec8f13be7d95ac96ebad826bc2d70d5fd5b88b0033085f4df  rnf05_local_384_4_B_20261108.json
```

El hash inicial de `local_validation_20261108.json` corresponde a la copia
anterior a añadir el resumen de carga sostenida; el hash actual es el segundo.
