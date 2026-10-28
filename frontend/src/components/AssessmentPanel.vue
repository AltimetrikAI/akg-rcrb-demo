<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['clear'])

const AGENTS = [
  { key: 'regulation', label: 'Regulation',  color: '#8b5cf6', border: '#8b5cf6' },
  { key: 'process',    label: 'Process',     color: '#10b981', border: '#10b981' },
  { key: 'systems',    label: 'Systems',     color: '#3b82f6', border: '#3b82f6' },
  { key: 'data',       label: 'Data',        color: '#f59e0b', border: '#f59e0b' },
  { key: 'synthesis',  label: 'Action Plan', color: '#e2e8f0', border: '#64748b' },
]

const FLOW_NODES = [
  {
    kg: 'Entity KG',
    agent: 'Regulation Agent',
    agentKey: 'regulation',
    color: '#8b5cf6',
    arrowLabel: 'GOVERNS (127 edges)',
  },
  {
    kg: 'Process KG',
    agent: 'Process Agent',
    agentKey: 'process',
    color: '#10b981',
    arrowLabel: 'EXECUTED_BY',
  },
  {
    kg: 'Systems KG',
    agent: 'Systems Agent',
    agentKey: 'systems',
    color: '#3b82f6',
    arrowLabel: 'USES_TABLE / MAPS_TO',
  },
  {
    kg: 'Data KG',
    agent: 'Data Agent',
    agentKey: 'data',
    color: '#f59e0b',
    arrowLabel: 'SYNTHESIS',
  },
  {
    kg: 'All KGs',
    agent: 'Synthesis Agent',
    agentKey: 'synthesis',
    color: '#e2e8f0',
    arrowLabel: null,
  },
]

const agentState = ref(
  Object.fromEntries(AGENTS.map(a => [a.key, { status: 'idle', content: '' }]))
)

// Which section is expanded (only one at a time; synthesis always visible when done)
const expanded = ref(null)

function setPending() {
  AGENTS.forEach(a => {
    agentState.value[a.key] = { status: 'pending', content: '' }
  })
  expanded.value = null
}

function setRunning(key) {
  if (agentState.value[key]) {
    agentState.value[key].status = 'running'
    expanded.value = key
  }
}

function appendContent(key, content) {
  if (agentState.value[key]) {
    agentState.value[key].content += content
    agentState.value[key].status = 'running'
    // Don't override user's manual tab selection — setRunning already switched
  }
}

function setDone(key) {
  if (agentState.value[key]) {
    agentState.value[key].status = 'done'
  }
}

function setAllDone() {
  AGENTS.forEach(a => {
    if (['running','pending'].includes(agentState.value[a.key].status)) {
      agentState.value[a.key].status = 'done'
    }
  })
  expanded.value = 'synthesis'
}

function clear() {
  AGENTS.forEach(a => {
    agentState.value[a.key] = { status: 'idle', content: '' }
  })
  expanded.value = null
  emit('clear')
}

function toggle(key) {
  expanded.value = expanded.value === key ? null : key
}

// ── Impact Flow helpers ────────────────────────────────────────────────────
function extractSummary(content) {
  if (!content) return ''
  const lines = content.split('\n')
  const meaningful = lines.filter(l => {
    const t = l.trim()
    return t && !t.startsWith('Traversing') && !t.startsWith('Querying')
  })
  const text = meaningful.join(' ').trim()
  return text.length > 200 ? text.slice(0, 200) + '...' : text
}

function statusLabel(status) {
  const map = { idle: 'IDLE', pending: 'WAITING', running: 'RUNNING', done: 'DONE' }
  return map[status] || status.toUpperCase()
}

function statusColor(status) {
  const map = { idle: '#334155', pending: '#64748b', running: '#f59e0b', done: '#10b981' }
  return map[status] || '#334155'
}

// ── Synthesis parse helpers ────────────────────────────────────────────────
function extractSection(content, heading) {
  const re = new RegExp(`##\\s+${heading}[\\s\\S]*?(?=\\n##\\s|$)`, 'i')
  const match = content.match(re)
  if (!match) return ''
  return match[0].replace(/^##[^\n]+\n/, '').trim()
}

function extractSystems(text) {
  const keywords = ['SAP', 'Java', 'MDG', 'ABAP', 'Peppol', 'CMDB']
  return [...new Set(keywords.filter(k => text.includes(k)))]
}

function extractPeppolFields(text) {
  return [...new Set((text.match(/B[TG]-\d+/g) || []))]
}

function parseActionItems(body) {
  const items = []
  const lines = body.split('\n')
  let current = null

  for (const line of lines) {
    const match = line.match(/^(\d+)\.\s+\*\*(.+?)\*\*(.*)$/)
    if (match) {
      if (current) items.push(current)
      const combined = match[2] + ' ' + match[3]
      current = {
        number: match[1],
        title: match[2],
        detail: match[3].replace(/^[\s—–-]+/, '').trim(),
        systems: extractSystems(combined),
        peppolFields: extractPeppolFields(combined),
      }
    } else if (current && line.trim()) {
      current.detail += ' ' + line.trim()
      current.systems = [...new Set([...current.systems, ...extractSystems(line)])]
      current.peppolFields = [...new Set([...current.peppolFields, ...extractPeppolFields(line)])]
    }
  }
  if (current) items.push(current)
  return items
}

function parseChangeActions(body) {
  const result = []
  const pSections = body.split(/\n(?=###\s)/)
  for (const pSec of pSections) {
    const firstLine = pSec.split('\n')[0].replace(/^###\s*/, '').trim()
    const pBody = pSec.replace(/^###[^\n]+\n/, '').trim()

    let priority = null
    let label = ''
    let color = ''

    if (/P1|BLOCKER/i.test(firstLine)) {
      priority = 'P1'; label = 'P1 — BLOCKERS'; color = '#ef4444'
    } else if (/P2|MANDATORY/i.test(firstLine)) {
      priority = 'P2'; label = 'P2 — MANDATORY'; color = '#f59e0b'
    } else if (/P3|CONFIRM/i.test(firstLine)) {
      priority = 'P3'; label = 'P3 — CONFIRMATIONS'; color = '#10b981'
    }

    if (priority) {
      result.push({ priority, label, color, items: parseActionItems(pBody) })
    }
  }
  return result
}

const parsedSynthesis = computed(() => {
  const content = agentState.value['synthesis']?.content || ''
  if (!content.includes('##')) return null

  const executive = extractSection(content, 'Executive Summary')
  const changeActionsRaw = extractSection(content, 'Change Actions Required')
  const timeline = extractSection(content, 'Timeline')
  const risk = extractSection(content, 'Critical Risk')

  const changeActions = changeActionsRaw ? parseChangeActions(changeActionsRaw) : []

  return { executive, changeActions, timeline, risk }
})

defineExpose({ setPending, setRunning, appendContent, setDone, setAllDone })
</script>

<template>
  <div class="panel">
    <!-- Header bar -->
    <div class="panel-header">
      <span class="panel-title">RCRB Assessment — Multi-Agent Analysis</span>
      <button class="clear-btn" @click="clear">Clear</button>
    </div>

    <!-- Agent tabs row -->
    <div class="tabs-row">
      <button
        v-for="agent in AGENTS"
        :key="agent.key"
        class="agent-tab"
        :class="{
          'tab-active':   expanded === agent.key,
          'tab-idle':     agentState[agent.key].status === 'idle',
          'tab-pending':  agentState[agent.key].status === 'pending',
          'tab-running':  agentState[agent.key].status === 'running',
          'tab-done':     agentState[agent.key].status === 'done',
        }"
        :style="expanded === agent.key ? { borderBottomColor: agent.color, color: agent.color } : {}"
        @click="toggle(agent.key)"
      >
        <span class="tab-dot"
          :class="{
            'dot-idle':    agentState[agent.key].status === 'idle',
            'dot-pending': agentState[agent.key].status === 'pending',
            'dot-running': agentState[agent.key].status === 'running',
            'dot-done':    agentState[agent.key].status === 'done',
          }"
        ></span>
        {{ agent.label }}
      </button>

      <!-- Virtual: Impact Flow tab -->
      <button
        class="agent-tab flow-tab"
        :class="{ 'tab-active': expanded === 'flow' }"
        :style="expanded === 'flow' ? { borderBottomColor: '#64748b', color: '#94a3b8' } : {}"
        @click="toggle('flow')"
      >
        <span class="tab-dot dot-flow"></span>
        Impact Flow
      </button>
    </div>

    <!-- Content area -->
    <div class="content-area">

      <!-- ── Impact Flow view ─────────────────────────────────────────── -->
      <div v-if="expanded === 'flow'" class="content-scroll flow-view">
        <div class="flow-chain">
          <template v-for="(node, idx) in FLOW_NODES" :key="node.agentKey">
            <div class="flow-node" :style="{ borderColor: node.color + '44' }">
              <!-- Left KG column -->
              <div class="flow-kg-col" :style="{ borderLeftColor: node.color }">
                <span class="flow-kg-label">{{ node.kg }}</span>
                <div class="flow-kg-line" :style="{ background: node.color + '33' }"></div>
              </div>
              <!-- Right agent info -->
              <div class="flow-agent-col">
                <div class="flow-agent-header">
                  <span class="flow-agent-dot" :style="{ background: node.color }"></span>
                  <span class="flow-agent-name" :style="{ color: node.color }">{{ node.agent }}</span>
                  <span
                    class="flow-status-badge"
                    :style="{
                      color: statusColor(agentState[node.agentKey]?.status || 'idle'),
                      borderColor: statusColor(agentState[node.agentKey]?.status || 'idle'),
                    }"
                  >{{ statusLabel(agentState[node.agentKey]?.status || 'idle') }}</span>
                </div>
                <div class="flow-agent-summary">
                  <template v-if="agentState[node.agentKey]?.status === 'done' || agentState[node.agentKey]?.status === 'running'">
                    <span class="flow-summary-text">
                      {{ extractSummary(agentState[node.agentKey]?.content) || 'Processing...' }}
                    </span>
                  </template>
                  <template v-else>
                    <span class="flow-summary-placeholder">
                      {{ agentState[node.agentKey]?.status === 'pending' ? 'Waiting to run...' : 'Not yet started' }}
                    </span>
                  </template>
                </div>
              </div>
            </div>
            <!-- Arrow between nodes -->
            <div v-if="idx < FLOW_NODES.length - 1" class="flow-arrow">
              <div class="flow-arrow-line"></div>
              <div class="flow-arrow-label">{{ node.arrowLabel }}</div>
              <div class="flow-arrow-head">&#9660;</div>
            </div>
          </template>
        </div>
      </div>

      <!-- ── Visual Synthesis view (when synthesis is done) ─────────── -->
      <div
        v-else-if="expanded === 'synthesis' && agentState['synthesis'].status === 'done' && parsedSynthesis"
        class="content-scroll synthesis-view"
      >
        <!-- Executive Summary -->
        <div v-if="parsedSynthesis.executive" class="syn-executive">
          <div class="syn-section-label">Executive Summary</div>
          <p class="syn-executive-text">{{ parsedSynthesis.executive }}</p>
        </div>

        <!-- Change Actions -->
        <template v-if="parsedSynthesis.changeActions && parsedSynthesis.changeActions.length">
          <div class="syn-section-label" style="margin-top: 16px;">Change Actions Required</div>
          <div
            v-for="group in parsedSynthesis.changeActions"
            :key="group.priority"
            class="syn-priority-group"
          >
            <div class="syn-priority-header" :style="{ color: group.color, borderLeftColor: group.color }">
              {{ group.label }}
            </div>
            <div class="syn-action-list">
              <div
                v-for="item in group.items"
                :key="item.number"
                class="syn-action-card"
                :style="{ borderLeftColor: group.color }"
              >
                <div class="syn-action-header">
                  <span class="syn-action-num" :style="{ color: group.color }">{{ item.number }}.</span>
                  <span class="syn-action-title">{{ item.title }}</span>
                </div>
                <div class="syn-action-badges">
                  <span
                    v-for="sys in item.systems"
                    :key="sys"
                    class="badge badge-sys"
                  >{{ sys }}</span>
                  <span
                    v-for="field in item.peppolFields"
                    :key="field"
                    class="badge badge-peppol"
                  >{{ field }}</span>
                </div>
                <div v-if="item.detail" class="syn-action-detail">{{ item.detail }}</div>
              </div>
            </div>
          </div>
        </template>

        <!-- Timeline -->
        <div v-if="parsedSynthesis.timeline" class="syn-timeline">
          <div class="syn-section-label" style="margin-top: 16px;">Timeline</div>
          <div class="syn-timeline-text">{{ parsedSynthesis.timeline }}</div>
        </div>

        <!-- Critical Risk -->
        <div v-if="parsedSynthesis.risk" class="syn-risk">
          <div class="syn-section-label" style="margin-top: 16px;">Critical Risk</div>
          <p class="syn-risk-text">{{ parsedSynthesis.risk }}</p>
        </div>
      </div>

      <!-- ── Synthesis running: show raw pre ─────────────────────────── -->
      <div
        v-else-if="expanded === 'synthesis' && agentState['synthesis'].status === 'running'"
        class="content-scroll"
      >
        <pre class="content-text streaming">{{ agentState['synthesis'].content }}</pre>
      </div>

      <!-- ── Idle / nothing selected ──────────────────────────────────── -->
      <div v-else-if="!expanded || agentState[expanded]?.status === 'idle'" class="placeholder">
        <span v-if="agentState['regulation'].status === 'idle'">
          Click "Run RCRB Assessment" to start the multi-agent analysis
        </span>
        <span v-else>Select an agent tab above to view its output</span>
      </div>

      <!-- ── Pending ──────────────────────────────────────────────────── -->
      <div v-else-if="agentState[expanded]?.status === 'pending'" class="placeholder">
        <span class="waiting">Waiting for agent...</span>
      </div>

      <!-- ── Running or done: show content ───────────────────────────── -->
      <div v-else class="content-scroll">
        <pre class="content-text" :class="{ streaming: agentState[expanded].status === 'running' }">{{ agentState[expanded].content }}</pre>
      </div>
    </div>

    <!-- Status strip: mini indicators for all agents -->
    <div class="status-strip">
      <div
        v-for="agent in AGENTS"
        :key="agent.key"
        class="strip-item"
        @click="toggle(agent.key)"
      >
        <span class="strip-dot"
          :style="agentState[agent.key].status === 'done' ? { background: agent.color } :
                  agentState[agent.key].status === 'running' ? { background: '#f59e0b' } : {}"
          :class="{
            'strip-dot-idle':    agentState[agent.key].status === 'idle',
            'strip-dot-running': agentState[agent.key].status === 'running',
          }"
        ></span>
        <span class="strip-label" :style="agentState[agent.key].status === 'done' ? { color: agent.color } : {}">
          {{ agent.label }}
        </span>
        <span class="strip-status">{{ agentState[agent.key].status }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e293b;
  overflow: hidden;
}

/* Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}
.panel-title {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.clear-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #64748b;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
}
.clear-btn:hover { border-color: #64748b; color: #f1f5f9; }

/* Agent tabs */
.tabs-row {
  display: flex;
  flex-shrink: 0;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  overflow: hidden;
}
.agent-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 10px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  letter-spacing: 0.02em;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
  flex-shrink: 1;
  min-width: 0;
}
.agent-tab:hover { color: #94a3b8; }
.tab-active { font-weight: 700; }
.tab-done { color: #94a3b8; }

.flow-tab {
  margin-left: auto;
  flex-shrink: 0;
  border-left: 1px solid #1e293b;
  color: #475569;
  font-style: italic;
}

/* Dots in tabs */
.tab-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-idle    { background: #334155; }
.dot-pending { background: #64748b; animation: blink 1.4s ease-in-out infinite; }
.dot-running { background: #f59e0b; animation: blink 0.6s ease-in-out infinite; }
.dot-done    { background: #10b981; }
.dot-flow    { background: #475569; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.2; }
}

/* Content area */
.content-area {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 13px;
  font-style: italic;
}
.waiting { color: #64748b; }

.content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
}
.content-scroll::-webkit-scrollbar { width: 5px; }
.content-scroll::-webkit-scrollbar-track { background: #0f172a; }
.content-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

.content-text {
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.75;
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
.content-text.streaming::after {
  content: '▋';
  display: inline;
  color: #f59e0b;
  animation: blink 0.6s step-end infinite;
}

/* ── Impact Flow view ──────────────────────────────────────────────────── */
.flow-view {
  padding: 16px;
}

.flow-chain {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.flow-node {
  display: flex;
  background: #0f172a;
  border: 1px solid;
  border-radius: 8px;
  overflow: hidden;
}

.flow-kg-col {
  width: 80px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14px 10px;
  border-left: 3px solid;
  background: rgba(255,255,255,0.015);
  border-right: 1px solid #1e293b;
  gap: 6px;
}

.flow-kg-label {
  font-size: 9px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-align: center;
  writing-mode: horizontal-tb;
}

.flow-kg-line {
  width: 100%;
  height: 2px;
  border-radius: 1px;
}

.flow-agent-col {
  flex: 1;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.flow-agent-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.flow-agent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.flow-agent-name {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}

.flow-status-badge {
  font-size: 9px;
  font-weight: 700;
  border: 1px solid;
  border-radius: 3px;
  padding: 2px 6px;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.flow-agent-summary {
  font-size: 11px;
  line-height: 1.5;
  min-height: 32px;
}

.flow-summary-text {
  color: #94a3b8;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  word-break: break-word;
}

.flow-summary-placeholder {
  color: #334155;
  font-style: italic;
}

.flow-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 0;
  gap: 0;
}

.flow-arrow-line {
  width: 1px;
  height: 10px;
  background: #334155;
}

.flow-arrow-label {
  font-size: 9px;
  color: #475569;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 8px;
  border: 1px solid #1e293b;
  border-radius: 3px;
  background: #0f172a;
  white-space: nowrap;
}

.flow-arrow-head {
  font-size: 10px;
  color: #334155;
  line-height: 1;
}

/* ── Visual Synthesis view ─────────────────────────────────────────────── */
.synthesis-view {
  padding: 14px 16px;
}

.syn-section-label {
  font-size: 10px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 8px;
}

.syn-executive {
  background: rgba(245, 158, 11, 0.05);
  border-left: 4px solid #f59e0b;
  border-radius: 0 6px 6px 0;
  padding: 12px 14px;
}

.syn-executive-text {
  font-size: 12px;
  color: #e2e8f0;
  line-height: 1.7;
  margin: 0;
}

.syn-priority-group {
  margin-bottom: 12px;
}

.syn-priority-header {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 6px 10px;
  border-left: 3px solid;
  background: rgba(255,255,255,0.02);
  border-radius: 0 4px 4px 0;
  margin-bottom: 6px;
}

.syn-action-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.syn-action-card {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-left: 3px solid;
  border-radius: 0 6px 6px 0;
  padding: 10px 12px;
}

.syn-action-header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 5px;
}

.syn-action-num {
  font-size: 12px;
  font-weight: 700;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  flex-shrink: 0;
}

.syn-action-title {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
  line-height: 1.4;
}

.syn-action-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 5px;
}

.badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  letter-spacing: 0.04em;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
}

.badge-sys {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.badge-peppol {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.syn-action-detail {
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
}

.syn-timeline {
  background: rgba(59, 130, 246, 0.04);
  border: 1px solid #1e3a5f;
  border-radius: 6px;
  padding: 12px 14px;
}

.syn-timeline-text {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.7;
  white-space: pre-wrap;
}

.syn-risk {
  background: rgba(239, 68, 68, 0.05);
  border-left: 4px solid #ef4444;
  border-radius: 0 6px 6px 0;
  padding: 12px 14px;
}

.syn-risk-text {
  font-size: 12px;
  color: #fca5a5;
  line-height: 1.7;
  margin: 0;
}

/* Status strip at bottom */
.status-strip {
  display: flex;
  align-items: center;
  padding: 6px 16px;
  gap: 20px;
  background: #0f172a;
  border-top: 1px solid #334155;
  flex-shrink: 0;
  overflow-x: auto;
}
.strip-item {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  flex-shrink: 0;
}
.strip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #334155;
  flex-shrink: 0;
}
.strip-dot-idle    { background: #334155; }
.strip-dot-running { background: #f59e0b; animation: blink 0.6s ease-in-out infinite; }
.strip-label {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.strip-status {
  font-size: 9px;
  color: #334155;
  text-transform: uppercase;
}
</style>
