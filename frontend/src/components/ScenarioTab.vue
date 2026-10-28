<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { fetchStats, fetchSemanticStatus } from '../api.js'

const props = defineProps({
  assessmentCompleted: { type: Boolean, default: false },
})

const stats = ref(null)
const statsError = ref(null)
const semanticStatus = ref(null)

// Only fetch compliance status after an assessment has run, not on initial load
watch(() => props.assessmentCompleted, async (completed) => {
  if (!completed) return
  try {
    semanticStatus.value = await fetchSemanticStatus()
  } catch (e) {
    // silently fail
  }
})

const readinessColor = computed(() => {
  const status = semanticStatus.value?.summary?.readiness_status
  if (status === 'READY') return '#10b981'
  if (status === 'NEAR_READY') return '#f59e0b'
  return '#ef4444'
})

const readinessScore = computed(() => {
  return semanticStatus.value?.summary?.readiness_score ?? 0
})

const regulationInput = ref('')
const countryInput = ref('BE')
const showTooltip = ref(false)

const SOURCE_GROUPS = [
  {
    label: 'ABAP',
    color: '#8b5cf6',
    files: [
      'INVOICE_CREATE',
      'VATCHECK',
      'PEPPOL_OUTPUT',
      'FI_TAXPOST',
    ],
  },
  {
    label: 'Java',
    color: '#10b981',
    files: [
      'InvoiceDeliveryService',
      'PeppolRouter',
      'CustomerVatService',
      'TaxDeterminationService',
      'BelgianVatValidator',
    ],
  },
  {
    label: 'CMDB',
    color: '#3b82f6',
    files: ['applications.json', 'services.json'],
  },
  {
    label: 'SAP Data Dictionary',
    color: '#f59e0b',
    files: ['tables.json', 'fields.json'],
  },
  {
    label: 'Regulations',
    color: '#94a3b8',
    files: ['belgium_einvoicing_decree_2022.txt'],
  },
  {
    label: 'SharePoint',
    color: '#64748b',
    files: [
      'Invoice_Process_Playbook.docx',
      'Peppol_Implementation_Guide.docx',
    ],
  },
]

const PIPELINE_STEPS = [
  {
    num: 1,
    label: 'Regulation Agent',
    color: '#8b5cf6',
    desc: 'Reads Entity KG for Peppol obligations',
  },
  {
    num: 2,
    label: 'Process Agent',
    color: '#10b981',
    desc: 'Traverses Process KG (ABAP + Java steps)',
  },
  {
    num: 3,
    label: 'Systems Agent',
    color: '#3b82f6',
    desc: 'Maps CMDB impact via Systems KG',
  },
  {
    num: 4,
    label: 'Data Agent',
    color: '#f59e0b',
    desc: 'Identifies SAP field gaps via Data KG',
  },
  {
    num: 5,
    label: 'Synthesis Agent',
    color: '#e2e8f0',
    desc: 'Produces structured Action Plan',
  },
]

const KG_CARDS = [
  {
    key: 'entity',
    label: 'Entity KG',
    color: '#8b5cf6',
    nodeLabels: ['Obligation', 'Regulation', 'Entity'],
    desc: 'Obligations, Regulation nodes',
  },
  {
    key: 'process',
    label: 'Process KG',
    color: '#10b981',
    nodeLabels: ['ProcessStep', 'BusinessFunction', 'Decision', 'Exception'],
    desc: 'ProcessStep, BusinessFunction, Decision, Exception',
  },
  {
    key: 'systems',
    label: 'Systems KG',
    color: '#3b82f6',
    nodeLabels: ['Application', 'ServiceOffering'],
    desc: 'Application nodes, ServiceOffering',
  },
  {
    key: 'data',
    label: 'Data KG',
    color: '#f59e0b',
    nodeLabels: ['Table', 'Column'],
    desc: 'Table, Column nodes',
  },
]

function getNodeCount(labels) {
  if (!stats.value?.node_counts) return '—'
  const total = stats.value.node_counts
    .filter(n => labels.includes(n.label))
    .reduce((sum, n) => sum + n.count, 0)
  return total || '—'
}

function totalFiles() {
  return SOURCE_GROUPS.reduce((s, g) => s + g.files.length, 0)
}

onMounted(async () => {
  try {
    stats.value = await fetchStats()
  } catch (e) {
    statsError.value = 'Could not reach backend'
  }
})
</script>

<template>
  <div class="scenario-tab">
    <!-- Top banner -->
    <div class="banner">
      <div class="banner-left">
        <div class="banner-title">Belgium B2B E-Invoicing — Regulatory Analysis</div>
        <div class="banner-subtitle">
          Royal Decree 9 March 2022 &middot; Peppol BIS 3.0 (UBL 2.1) &middot; Mandatory 2026-01-01
        </div>
      </div>
      <div class="banner-center">
        <div v-if="semanticStatus === null" class="readiness-loading">Loading...</div>
        <template v-else>
          <div
            class="score-ring"
            :style="{ background: `conic-gradient(${readinessColor} ${readinessScore}%, #1e293b ${readinessScore}%)` }"
          >
            <div class="score-inner">{{ readinessScore }}</div>
          </div>
          <div
            class="readiness-label"
            :style="{
              color: readinessColor
            }"
          >{{ semanticStatus.summary.status }}</div>
          <div class="readiness-blockers">
            {{ semanticStatus.summary.need_change }} changes required
          </div>
        </template>
      </div>
      <div class="banner-right">
        <span class="status-badge">ACTIVE SCENARIO</span>
      </div>
    </div>

    <!-- 3-column grid -->
    <div class="grid">
      <!-- Column A: Source Data Ingested -->
      <div class="col col-a">
        <div class="col-header">
          <span class="col-title">Source Data Ingested</span>
          <span class="col-count">{{ totalFiles() }} files</span>
        </div>
        <div class="source-groups">
          <div
            v-for="group in SOURCE_GROUPS"
            :key="group.label"
            class="source-group"
          >
            <div class="source-group-header">
              <span class="source-group-dot" :style="{ background: group.color }"></span>
              <span class="source-group-label">{{ group.label }}</span>
              <span class="source-group-count">{{ group.files.length }}</span>
            </div>
            <div class="source-files">
              <div
                v-for="file in group.files"
                :key="file"
                class="source-file"
                :style="{ borderLeftColor: group.color }"
              >
                {{ file }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Column B: 5-Agent Analysis Pipeline -->
      <div class="col col-b">
        <div class="col-header">
          <span class="col-title">5-Agent Analysis Pipeline</span>
        </div>
        <div class="pipeline">
          <template v-for="(step, idx) in PIPELINE_STEPS" :key="step.num">
            <div class="pipeline-step">
              <div class="step-dot" :style="{ background: step.color, boxShadow: `0 0 8px ${step.color}55` }"></div>
              <div class="step-body">
                <div class="step-num" :style="{ color: step.color }">Agent {{ step.num }}</div>
                <div class="step-label" :style="{ color: step.color }">{{ step.label }}</div>
                <div class="step-desc">{{ step.desc }}</div>
              </div>
            </div>
            <div v-if="idx < PIPELINE_STEPS.length - 1" class="pipeline-arrow">
              <div class="arrow-line"></div>
              <div class="arrow-head">&#9660;</div>
            </div>
          </template>
        </div>
      </div>

      <!-- Column C: Knowledge Graph Network -->
      <div class="col col-c">
        <div class="col-header">
          <span class="col-title">Knowledge Graph Network</span>
          <span v-if="statsError" class="col-error">{{ statsError }}</span>
        </div>
        <div class="kg-grid">
          <div
            v-for="kg in KG_CARDS"
            :key="kg.key"
            class="kg-card"
            :style="{ borderColor: kg.color + '55' }"
          >
            <div class="kg-card-header">
              <span class="kg-card-dot" :style="{ background: kg.color }"></span>
              <span class="kg-card-label" :style="{ color: kg.color }">{{ kg.label }}</span>
            </div>
            <div class="kg-card-count" :style="{ color: kg.color }">
              {{ getNodeCount(kg.nodeLabels) }}
            </div>
            <div class="kg-card-desc">{{ kg.desc }}</div>
          </div>
        </div>
        <div class="kg-edges" v-if="stats">
          <span class="kg-edges-label">Total Edges</span>
          <span class="kg-edges-count">{{ stats.total_edges?.toLocaleString() ?? '—' }}</span>
          <span class="kg-edges-sub">relationships</span>
        </div>
      </div>
    </div>

    <!-- Bottom bar: Scenario Input -->
    <div class="bottom-bar">
      <span class="bottom-label">Analyze a different regulation:</span>
      <input
        v-model="regulationInput"
        class="regulation-input"
        type="text"
        placeholder="e.g. France Factur-X 2026"
      />
      <select v-model="countryInput" class="country-select">
        <option value="BE">BE</option>
        <option value="FR">FR</option>
        <option value="DE">DE</option>
        <option value="NL">NL</option>
      </select>
      <div
        class="load-btn-wrapper"
        @mouseenter="showTooltip = true"
        @mouseleave="showTooltip = false"
      >
        <button class="load-btn" disabled>Load &amp; Run</button>
        <div v-if="showTooltip" class="tooltip">Coming Soon</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: #0f172a;
}

/* Banner */
.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}

.banner-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.banner-title {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.01em;
}

.banner-subtitle {
  font-size: 12px;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  letter-spacing: 0.02em;
}

/* Banner center: compliance readiness */
.banner-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 80px;
  flex-shrink: 0;
}

.readiness-loading {
  font-size: 11px;
  color: #475569;
}

.score-ring {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-inner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #f1f5f9;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
}

.readiness-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-align: center;
  line-height: 1.2;
}

.readiness-blockers {
  font-size: 10px;
  color: #ef4444;
  text-align: center;
  line-height: 1.2;
}

.status-badge {
  font-size: 11px;
  font-weight: 700;
  color: #10b981;
  border: 1px solid #10b981;
  border-radius: 4px;
  padding: 4px 10px;
  letter-spacing: 0.08em;
  background: rgba(16, 185, 129, 0.06);
}

/* 3-column grid */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  gap: 0;
  border-bottom: 1px solid #334155;
}

.col {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #334155;
  padding: 0;
}

.col:last-child {
  border-right: none;
}

.col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px 8px;
  border-bottom: 1px solid #1e293b;
  flex-shrink: 0;
  background: rgba(255,255,255,0.02);
}

.col-title {
  font-size: 10px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.col-count {
  font-size: 10px;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
}

.col-error {
  font-size: 10px;
  color: #f87171;
}

/* Column A: Source Groups */
.source-groups {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-groups::-webkit-scrollbar { width: 4px; }
.source-groups::-webkit-scrollbar-track { background: #0f172a; }
.source-groups::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

.source-group {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  overflow: hidden;
}

.source-group-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  background: rgba(255,255,255,0.02);
  border-bottom: 1px solid #334155;
}

.source-group-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.source-group-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  flex: 1;
}

.source-group-count {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  background: #0f172a;
  border-radius: 3px;
  padding: 1px 5px;
}

.source-files {
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.source-file {
  font-size: 10px;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  color: #64748b;
  padding: 2px 6px;
  border-left: 2px solid;
  background: rgba(255,255,255,0.015);
  border-radius: 0 2px 2px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Column B: Pipeline */
.pipeline {
  flex: 1;
  overflow-y: auto;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pipeline::-webkit-scrollbar { width: 4px; }
.pipeline::-webkit-scrollbar-track { background: #0f172a; }
.pipeline::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

.pipeline-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px 14px;
}

.step-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 3px;
}

.step-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.step-num {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.7;
}

.step-label {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.step-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.pipeline-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 0;
  color: #334155;
  flex-shrink: 0;
}

.arrow-line {
  width: 1px;
  height: 14px;
  background: #334155;
}

.arrow-head {
  font-size: 10px;
  color: #475569;
  line-height: 1;
}

/* Column C: KG Cards */
.kg-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 12px;
}

.kg-card {
  background: #1e293b;
  border: 1px solid;
  border-radius: 8px;
  padding: 12px;
}

.kg-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.kg-card-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.kg-card-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.kg-card-count {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 4px;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
}

.kg-card-desc {
  font-size: 9px;
  color: #475569;
  line-height: 1.4;
}

.kg-edges {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 0 12px 12px;
  border-top: 1px solid #1e293b;
  margin: 0 12px;
  padding-top: 10px;
}

.kg-edges-label {
  font-size: 10px;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}

.kg-edges-count {
  font-size: 18px;
  font-weight: 700;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
}

.kg-edges-sub {
  font-size: 10px;
  color: #334155;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* Bottom bar */
.bottom-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #1e293b;
  border-top: 1px solid #334155;
  flex-shrink: 0;
}

.bottom-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  font-weight: 500;
}

.regulation-input {
  flex: 1;
  max-width: 280px;
  padding: 6px 10px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}

.regulation-input:focus {
  border-color: #475569;
}

.regulation-input::placeholder {
  color: #334155;
}

.country-select {
  padding: 6px 8px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 12px;
  outline: none;
  cursor: pointer;
}

.load-btn-wrapper {
  position: relative;
}

.load-btn {
  padding: 6px 16px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: not-allowed;
  letter-spacing: 0.02em;
}

.tooltip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  pointer-events: none;
}

.tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #334155;
}
</style>
