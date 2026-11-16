// Carga sostenida local contra /api/chat/query.
//
// A diferencia de k6_load.js (un burst de 100 solicitudes), este escenario:
// - crea una conversación independiente por solicitud antes de medir;
// - ejecuta N iteraciones por VU con una pausa configurable;
// - permite observar latencia y errores durante varios segundos/minutos.
//
// Uso local (no producción):
//   EVAL_API_URL=http://127.0.0.1:8001 \
//   EVAL_TOKEN=<jwt-local> EVAL_VUS=8 EVAL_ITERATIONS_PER_VU=30 \
//   EVAL_SLEEP_S=1 k6 run eval/k6_sustained.js
//
// Sin LLM/embeddings/judge/stt/tts, esto mide el harness y la API local; no es
// una medición de capacidad de producción ni del SLO de 3 s.

import http from 'k6/http'
import { check, fail, sleep } from 'k6'
import { SharedArray } from 'k6/data'
import { Counter, Rate, Trend } from 'k6/metrics'

const API_URL = __ENV.EVAL_API_URL || 'http://localhost:8000'
const TOKEN = __ENV.EVAL_TOKEN || ''
const VUS = Number(__ENV.EVAL_VUS || 5)
const ITERATIONS_PER_VU = Number(__ENV.EVAL_ITERATIONS_PER_VU || 30)
const SLEEP_S = Number(__ENV.EVAL_SLEEP_S || 1)
const MAX_DURATION = __ENV.EVAL_MAX_DURATION || '30m'

if (!TOKEN) {
  throw new Error('EVAL_TOKEN es obligatorio; no ejecutar carga anónima accidentalmente')
}
if (!Number.isInteger(VUS) || VUS < 1) {
  throw new Error('EVAL_VUS debe ser un entero >= 1')
}
if (!Number.isInteger(ITERATIONS_PER_VU) || ITERATIONS_PER_VU < 1) {
  throw new Error('EVAL_ITERATIONS_PER_VU debe ser un entero >= 1')
}
if (!Number.isFinite(SLEEP_S) || SLEEP_S < 0) {
  throw new Error('EVAL_SLEEP_S debe ser >= 0')
}

const chatStatus = new Counter('chat_query_status')
const chatSuccessRate = new Rate('chat_query_success_rate')
const chatSuccessDuration = new Trend('chat_query_success_duration', true)
const chatAllDuration = new Trend('chat_query_all_duration', true)

const dataset = new SharedArray('gold', function () {
  const data = JSON.parse(open('../eval/gold_dataset.json'))
  return data.items.map((i) => i.pregunta)
})

export const options = {
  scenarios: {
    chat_query_sustained: {
      executor: 'per-vu-iterations',
      vus: VUS,
      iterations: ITERATIONS_PER_VU,
      maxDuration: MAX_DURATION,
    },
  },
  thresholds: {
    chat_query_success_rate: ['rate>=0.95'],
    chat_query_success_duration: ['p(95)<=3000'],
  },
}

const headers = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${TOKEN}`,
}

export function setup() {
  const totalRequests = VUS * ITERATIONS_PER_VU
  const conversations = []
  for (let i = 0; i < totalRequests; i += 1) {
    const response = http.post(`${API_URL}/api/conversations/`, null, {
      headers,
      tags: { endpoint: 'conversation_setup' },
    })
    if (response.status !== 201) {
      fail(`No se pudo crear conversación de prueba: HTTP ${response.status}`)
    }
    conversations.push(response.json('id'))
  }
  return { conversations }
}

export default function (data) {
  const index = (__VU - 1) * ITERATIONS_PER_VU + __ITER
  const conversationId = data.conversations[index]
  const question = dataset[index % dataset.length]

  const res = http.post(
    `${API_URL}/api/chat/query`,
    JSON.stringify({ conversation_id: conversationId, message: question }),
    { headers, tags: { endpoint: 'chat_query' } },
  )
  chatStatus.add(1, { status: String(res.status) })
  chatSuccessRate.add(res.status === 200)
  chatAllDuration.add(res.timings.duration)
  if (res.status === 200) chatSuccessDuration.add(res.timings.duration)

  check(res, {
    'status 200': (r) => r.status === 200,
    'responde con texto': (r) => r.status === 200 && typeof r.json().response === 'string',
  })

  if (SLEEP_S > 0) sleep(SLEEP_S)
}
