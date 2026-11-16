// Prueba HTTP de carga contra /api/chat/query.
// Ejecutar desde la raíz del backend:
//   EVAL_API_URL=https://staging.example EVAL_TOKEN=<jwt> \
//   EVAL_VUS=50 EVAL_MIN_REQUESTS=100 k6 run eval/k6_load.js
//
// Requiere un entorno de pruebas y un JWT válido. El script prepara conversaciones
// antes del escenario de carga y asigna una distinta a cada solicitud para evitar
// carreras e historial compartido. El rate limit del servidor no se desactiva aquí:
// los 429 se contabilizan; para medir capacidad del backend se debe configurar una
// regla de staging explícita y registrar esa configuración.
import http from 'k6/http'
import { check, fail } from 'k6'
import { SharedArray } from 'k6/data'
import { Counter, Rate, Trend } from 'k6/metrics'

const API_URL = __ENV.EVAL_API_URL || 'http://localhost:8000'
const TOKEN = __ENV.EVAL_TOKEN || ''
const VUS = Number(__ENV.EVAL_VUS || 1)
const MIN_REQUESTS = Number(__ENV.EVAL_MIN_REQUESTS || 100)
const ITERATIONS_PER_VU = Math.ceil(MIN_REQUESTS / VUS)
const MAX_DURATION = __ENV.EVAL_MAX_DURATION || '30m'

if (!TOKEN) {
  throw new Error('EVAL_TOKEN es obligatorio; no ejecutar carga anónima accidentalmente')
}
if (!Number.isInteger(VUS) || VUS < 1 || !Number.isInteger(MIN_REQUESTS) || MIN_REQUESTS < 100) {
  throw new Error('EVAL_VUS debe ser >= 1 y EVAL_MIN_REQUESTS debe ser >= 100')
}

const chatStatus = new Counter('chat_query_status')
const chatSuccessRate = new Rate('chat_query_success_rate')
const chatSuccessDuration = new Trend('chat_query_success_duration', true)
const chatAllDuration = new Trend('chat_query_all_duration', true)

const dataset = new SharedArray('gold', function () {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const data = JSON.parse(open('../eval/gold_dataset.json'))
  return data.items.map((i) => i.pregunta)
})

export const options = {
  scenarios: {
    chat_query: {
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
  const conversations = []
  const totalRequests = VUS * ITERATIONS_PER_VU
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
  const iterationIndex = (__VU - 1) * ITERATIONS_PER_VU + __ITER
  const conversationId = data.conversations[iterationIndex]
  const question = dataset[iterationIndex % dataset.length]

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
}
