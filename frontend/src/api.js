const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.url}`)
  return res.json()
}

export function fetchStats() {
  return get('/stats')
}

export function fetchObligations() {
  return get('/obligations')
}

export function fetchApplications() {
  return get('/applications')
}

export function fetchProcessSteps() {
  return get('/process-steps')
}

export function fetchGraph(kg = null) {
  if (kg) return get(`/graph/kg/${kg}`)
  return get('/graph/all')
}

export function fetchImpactPath(obligationId) {
  return get(`/graph/impact-path?obligation_id=${encodeURIComponent(obligationId)}`)
}

/**
 * Stream assessment via SSE.
 * @param {function} onAgent - called with {agent, content} for each agent event
 * @param {function} onDone  - called when stream completes
 * @returns {function} cancel - call to abort the stream
 */
export function streamAssessment(onAgent, onDone, regulation = 'Belgium Mandatory B2B E-Invoicing', country = 'BE') {
  const params = new URLSearchParams({ regulation, country })
  const url = `${BASE}/assess?${params}`
  const es = new EventSource(url)

  // Backend emits named events: "agent_result" and "done"
  es.addEventListener('agent_result', (event) => {
    try {
      const data = JSON.parse(event.data)
      onAgent(data)
    } catch (e) {
      console.error('SSE parse error', e)
    }
  })

  es.addEventListener('done', () => {
    onDone()
    es.close()
  })

  es.onerror = (err) => {
    console.error('SSE error', err)
    onDone()
    es.close()
  }

  return () => es.close()
}

// ── Semantic Layer ───────────────────────────────────────────────────────────

export function fetchSemanticStatus(country = 'BE') {
  return get(`/semantic/status?country=${country}`)
}

export function fetchReadinessScore(country = 'BE') {
  return get(`/semantic/readiness?country=${country}`)
}

export function fetchSemanticConfig() {
  return get('/semantic/config')
}

export function updateSemanticConfig(updates) {
  return fetch('/api/semantic/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}

// ── HITL Validation ─────────────────────────────────────────────────────────

export function fetchValidationGraph() {
  return get('/validate/process')
}

export function updateNodeValidation(nodeId, data) {
  return fetch(`${BASE}/validate/node/${encodeURIComponent(nodeId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}

export function addRelationship(fromId, toId, label = 'CALLS') {
  return fetch(`${BASE}/validate/relationship`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_id: fromId, to_id: toId, label }),
  }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}

export function removeRelationship(fromId, toId, label = 'CALLS') {
  return fetch(`${BASE}/validate/relationship`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_id: fromId, to_id: toId, label }),
  }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}

export function fetchSources() {
  return get('/sources')
}

export function fetchSourceFile(filename) {
  return get(`/source/${encodeURIComponent(filename)}`)
}
