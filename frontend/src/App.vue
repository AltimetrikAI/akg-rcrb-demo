<script setup>
import { ref, onMounted } from 'vue'
import GraphViz from './components/GraphViz.vue'
import AssessmentPanel from './components/AssessmentPanel.vue'
import SourceExplorer from './components/SourceExplorer.vue'
import ScenarioTab from './components/ScenarioTab.vue'
import ProcessFlowView from './components/ProcessFlowView.vue'
import ValidateTab from './components/ValidateTab.vue'
import SemanticLayerTab from './components/SemanticLayerTab.vue'
import { fetchStats, fetchGraph, streamAssessment } from './api.js'

const resetting = ref(false)

async function resetDemo() {
  if (resetting.value) return
  resetting.value = true
  try {
    await fetch('/api/demo/reset', { method: 'POST' })
    assessmentCompleted.value = false
    assessmentRunning.value = false
    if (cancelStream) { cancelStream(); cancelStream = null }
    assessmentRef.value?.reset?.()
    window.location.reload()
  } catch (e) {
    console.error('Reset failed', e)
    resetting.value = false
  }
}

// ── Tab state ──────────────────────────────────────────────────────────────
const activeTab = ref('scenario')

// ── State ──────────────────────────────────────────────────────────────────
const stats = ref(null)
const statsError = ref(null)
const graphData = ref({ nodes: [], edges: [] })
const graphLoading = ref(false)
const graphError = ref(null)
const activeKg = ref(null)

const assessmentRunning = ref(false)
const assessmentCompleted = ref(false)
const graphVizRef = ref(null)
const assessmentRef = ref(null)

let cancelStream = null

const KG_LIST = [
  { key: 'systems', label: 'Systems KG',  color: '#3b82f6', desc: 'CMDB Applications' },
  { key: 'process', label: 'Process KG',  color: '#10b981', desc: 'ABAP/Java Steps' },
  { key: 'data',    label: 'Data KG',     color: '#f59e0b', desc: 'SAP Tables/Columns' },
  { key: 'entity',  label: 'Entity KG',   color: '#8b5cf6', desc: 'Regulatory Entities' }
]

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    stats.value = await fetchStats()
  } catch (e) {
    statsError.value = 'Could not reach backend'
    console.error(e)
  }
})

// ── KG Selection ───────────────────────────────────────────────────────────
async function selectKg(kg) {
  if (activeKg.value === kg) return
  activeKg.value = kg
  graphLoading.value = true
  graphError.value = null
  graphData.value = { nodes: [], edges: [] }

  try {
    graphData.value = await fetchGraph(kg)
  } catch (e) {
    graphError.value = 'Failed to load graph data'
    console.error(e)
  } finally {
    graphLoading.value = false
  }
}

// ── Assessment ─────────────────────────────────────────────────────────────
function runAssessment() {
  if (assessmentRunning.value) return

  if (cancelStream) {
    cancelStream()
    cancelStream = null
  }

  assessmentRunning.value = true
  activeTab.value = 'graphs'
  assessmentRef.value?.setPending()

  // Track which agents have started so we only setRunning once
  const started = new Set()

  cancelStream = streamAssessment(
    ({ agent, content }) => {
      if (!started.has(agent)) {
        started.add(agent)
        assessmentRef.value?.setRunning(agent)
      }
      assessmentRef.value?.appendContent(agent, content)
    },
    () => {
      assessmentRef.value?.setAllDone()
      assessmentRunning.value = false
      assessmentCompleted.value = true
      cancelStream = null
    },
    'Belgium Mandatory B2B E-Invoicing',
    'BE'
  )
}

function onAssessmentClear() {
  if (cancelStream) {
    cancelStream()
    cancelStream = null
  }
  assessmentRunning.value = false
}

// ── Stats helpers ──────────────────────────────────────────────────────────
function getKgCount(kgKey) {
  if (!stats.value || !stats.value.node_counts) return '—'
  const kgLabelMap = {
    systems: ['Application', 'ServiceOffering'],
    process: ['ProcessStep', 'BusinessFunction'],
    data: ['Table', 'Column'],
    entity: ['Obligation', 'Regulation', 'Entity']
  }
  const labels = kgLabelMap[kgKey] || []
  const total = stats.value.node_counts
    .filter(n => labels.includes(n.label))
    .reduce((sum, n) => sum + n.count, 0)
  return total || '—'
}
</script>

<template>
  <div class="app">
    <!-- ── Header ─────────────────────────────────────────────────────── -->
    <header class="header">
      <div class="header-left">
        <div class="header-logo">
          <div class="logo-mark">AKG</div>
        </div>
        <div class="header-titles">
          <span class="header-title">Agentic Knowledge Graph Platform</span>
          <span class="header-subtitle">Regulatory Change Impact Analysis</span>
        </div>
      </div>
      <div class="header-right">
        <div v-if="stats" class="header-stat">
          <span class="stat-val">{{ stats.total_edges?.toLocaleString() ?? '—' }}</span>
          <span class="stat-label">total edges</span>
        </div>
        <div v-if="stats" class="header-stat">
          <span class="stat-val">
            {{ (stats.node_counts || []).reduce((s, n) => s + n.count, 0).toLocaleString() }}
          </span>
          <span class="stat-label">total nodes</span>
        </div>
        <button
          class="reset-btn"
          :disabled="resetting || assessmentRunning"
          @click="resetDemo"
        >
          {{ resetting ? 'Resetting...' : 'Reset Demo' }}
        </button>
        <button
          class="run-btn"
          :class="{ 'run-btn--active': assessmentRunning }"
          :disabled="assessmentRunning"
          @click="runAssessment"
        >
          <span class="run-dot" :class="{ 'run-dot--pulse': assessmentRunning }"></span>
          {{ assessmentRunning ? 'Assessment Running...' : 'Run RCRB Assessment' }}
        </button>
      </div>
    </header>

    <!-- ── Tab bar ───────────────────────────────────────────────────── -->
    <nav class="tab-bar">
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'scenario' }"
        @click="activeTab = 'scenario'"
      >Scenario</button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'graphs' }"
        @click="activeTab = 'graphs'"
      >Knowledge Graphs</button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'process-flow' }"
        @click="activeTab = 'process-flow'"
      >
        <span class="tab-indicator-dot"></span>
        Process Flow
      </button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'source' }"
        @click="activeTab = 'source'"
      >Source Data</button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'semantic' }"
        @click="activeTab = 'semantic'"
      >Semantic Layer</button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'validate' }"
        @click="activeTab = 'validate'"
      >Validate</button>
    </nav>

    <!-- ── Scenario tab ───────────────────────────────────────────────── -->
    <ScenarioTab v-if="activeTab === 'scenario'" class="scenario-full" :assessmentCompleted="assessmentCompleted" />

    <!-- ── Process Flow ──────────────────────────────────────────────── -->
    <ProcessFlowView v-else-if="activeTab === 'process-flow'" class="process-flow-full" :assessmentCompleted="assessmentCompleted" />

    <!-- ── Source Explorer ────────────────────────────────────────────── -->
    <SourceExplorer v-else-if="activeTab === 'source'" />

    <!-- ── Semantic Layer ──────────────────────────────────────────── -->
    <SemanticLayerTab v-else-if="activeTab === 'semantic'" class="semantic-full" />

    <!-- ── Validate (HITL) ──────────────────────────────────────────── -->
    <ValidateTab v-else-if="activeTab === 'validate'" class="validate-full" />

    <!-- ── Body ──────────────────────────────────────────────────────── -->
    <div v-else-if="activeTab === 'graphs'" class="body">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-label">Knowledge Graphs</div>
          <button
            v-for="kg in KG_LIST"
            :key="kg.key"
            class="kg-btn"
            :class="{ 'kg-btn--active': activeKg === kg.key }"
            :style="activeKg === kg.key ? { borderColor: kg.color, color: kg.color } : {}"
            @click="selectKg(kg.key)"
          >
            <span class="kg-dot" :style="{ background: kg.color }"></span>
            <div class="kg-btn-text">
              <span class="kg-btn-label">{{ kg.label }}</span>
              <span class="kg-btn-desc">{{ kg.desc }}</span>
            </div>
            <span v-if="activeKg === kg.key" class="kg-check">&#10003;</span>
          </button>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-section-label">Graph Statistics</div>
          <div v-if="statsError" class="stats-error">{{ statsError }}</div>
          <div v-else-if="!stats" class="stats-loading">Loading...</div>
          <div v-else class="stats-grid">
            <div
              v-for="kg in KG_LIST"
              :key="kg.key"
              class="stat-card"
              :style="{ borderColor: activeKg === kg.key ? kg.color : '#334155' }"
            >
              <div class="stat-card-header">
                <span class="stat-card-dot" :style="{ background: kg.color }"></span>
                <span class="stat-card-name">{{ kg.label }}</span>
              </div>
              <div class="stat-card-count" :style="{ color: kg.color }">{{ getKgCount(kg.key) }}</div>
              <div class="stat-card-label">nodes</div>
            </div>

            <div class="stat-card stat-card--full">
              <div class="stat-card-header">
                <span class="stat-card-name">All Edges</span>
              </div>
              <div class="stat-card-count" style="color: #64748b">
                {{ stats.total_edges?.toLocaleString() ?? '—' }}
              </div>
              <div class="stat-card-label">relationships</div>
            </div>
          </div>

          <div v-if="stats && stats.node_counts && stats.node_counts.length" class="node-breakdown">
            <div class="breakdown-title">Node Breakdown</div>
            <div
              v-for="n in stats.node_counts"
              :key="n.label"
              class="breakdown-row"
            >
              <span class="breakdown-label">{{ n.label }}</span>
              <span class="breakdown-count">{{ n.count }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main area -->
      <main class="main">
        <!-- Graph panel -->
        <div class="graph-panel">
          <div class="panel-topbar">
            <span class="panel-topbar-title">
              Graph Visualization
              <span v-if="activeKg" class="panel-topbar-sub">— {{ activeKg }} KG</span>
            </span>
            <span v-if="graphLoading" class="topbar-loading">Loading graph...</span>
            <span v-if="graphError" class="topbar-error">{{ graphError }}</span>
          </div>
          <div class="graph-body">
            <GraphViz ref="graphVizRef" :graphData="graphData" />
          </div>
        </div>

        <!-- Assessment panel -->
        <div class="assessment-panel">
          <AssessmentPanel ref="assessmentRef" @clear="onAssessmentClear" />
        </div>
      </main>
    </div>
  </div>
</template>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body, #app {
  height: 100%;
  width: 100%;
}

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f172a;
  color: #f1f5f9;
  font-size: 14px;
  overflow: hidden;
}
</style>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ── Header ─────────────────────────────────────────────────────────────── */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 58px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-logo {
  flex-shrink: 0;
}

.logo-mark {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #fff;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-title {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.01em;
}

.header-subtitle {
  font-size: 11px;
  color: #64748b;
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
}

.header-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}

.stat-val {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1;
}

.stat-label {
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.reset-btn {
  padding: 8px 14px;
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
  letter-spacing: 0.02em;
}

.reset-btn:hover:not(:disabled) {
  border-color: #ef4444;
  color: #f87171;
}

.reset-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.run-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  background: #1e3a5f;
  border: 1px solid #3b82f6;
  color: #93c5fd;
  font-size: 13px;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  letter-spacing: 0.02em;
}

.run-btn:hover:not(:disabled) {
  background: #2563eb;
  border-color: #60a5fa;
  color: #fff;
}

.run-btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.run-btn--active {
  background: #1e3a5f;
  border-color: #f59e0b;
  color: #fcd34d;
}

.run-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

.run-dot--pulse {
  background: #f59e0b;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}

/* ── Tab bar ────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  align-items: stretch;
  gap: 0;
  height: 36px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  padding: 0 16px;
}

.tab {
  display: inline-flex;
  align-items: center;
  padding: 0 16px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  letter-spacing: 0.01em;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}

.tab:hover {
  color: #94a3b8;
}

.tab--active {
  color: #f1f5f9;
  border-bottom-color: #3b82f6;
}

/* ── Tab dot indicator ──────────────────────────────────────────────────── */
.tab-indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  flex-shrink: 0;
  margin-right: 5px;
}

/* ── Scenario full-width ─────────────────────────────────────────────────── */
.scenario-full {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Process Flow full-width ─────────────────────────────────────────────── */
.process-flow-full {
  flex: 1;
  min-height: 0;
}

/* ── Semantic Layer full-width ───────────────────────────────────────────── */
.semantic-full {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

/* ── Validate full-width ─────────────────────────────────────────────────── */
.validate-full {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Body ───────────────────────────────────────────────────────────────── */
.body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.sidebar {
  width: 320px;
  flex-shrink: 0;
  background: #1e293b;
  border-right: 1px solid #334155;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar::-webkit-scrollbar {
  width: 5px;
}
.sidebar::-webkit-scrollbar-track { background: #0f172a; }
.sidebar::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

.sidebar-section {
  padding: 16px;
  border-bottom: 1px solid #334155;
}

.sidebar-section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #475569;
  margin-bottom: 10px;
}

/* KG buttons */
.kg-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  margin-bottom: 6px;
  text-align: left;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kg-btn:last-child {
  margin-bottom: 0;
}

.kg-btn:hover {
  background: rgba(255,255,255,0.03);
  border-color: #475569;
  color: #f1f5f9;
}

.kg-btn--active {
  background: rgba(255,255,255,0.04);
}

.kg-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.kg-btn-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.kg-btn-label {
  font-size: 13px;
  font-weight: 600;
}

.kg-btn-desc {
  font-size: 10px;
  color: #64748b;
}

.kg-check {
  font-size: 12px;
  flex-shrink: 0;
}

/* Stats */
.stats-error {
  font-size: 12px;
  color: #f87171;
}

.stats-loading {
  font-size: 12px;
  color: #64748b;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 12px;
}

.stat-card {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 8px 10px;
  transition: border-color 0.2s;
}

.stat-card--full {
  grid-column: span 2;
}

.stat-card-header {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 4px;
}

.stat-card-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-card-name {
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.stat-card-count {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 1px;
}

.stat-card-label {
  font-size: 9px;
  color: #334155;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Node breakdown */
.node-breakdown {
  margin-top: 4px;
}

.breakdown-title {
  font-size: 10px;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-bottom: 6px;
}

.breakdown-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #1e293b;
}

.breakdown-label {
  font-size: 11px;
  color: #94a3b8;
}

.breakdown-count {
  font-size: 11px;
  color: #f1f5f9;
  font-weight: 600;
}

/* ── Main area ──────────────────────────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: row;
  min-width: 0;
  overflow: hidden;
  gap: 0;
}

/* Graph panel — 58% width */
.graph-panel {
  flex: 58;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border-right: 1px solid #334155;
}

.panel-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}

.panel-topbar-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.panel-topbar-sub {
  color: #64748b;
  font-weight: 400;
  text-transform: none;
}

.topbar-loading {
  font-size: 11px;
  color: #f59e0b;
}

.topbar-error {
  font-size: 11px;
  color: #f87171;
}

.graph-body {
  flex: 1;
  min-height: 0;
  padding: 0;
}

/* Assessment panel — 42% width, full height */
.assessment-panel {
  flex: 42;
  min-width: 360px;
  min-height: 0;
  overflow: hidden;
}
</style>
