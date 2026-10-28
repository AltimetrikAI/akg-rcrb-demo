<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchSemanticConfig, updateSemanticConfig, fetchSemanticStatus } from '../api.js'

// ── State ──────────────────────────────────────────────────────────────────
const status = ref(null)
const configLoading = ref(false)
const statusLoading = ref(false)
const configError = ref(null)

// Impact levels
const impactLevels = ref({ HIGH: '', MEDIUM: '', LOW: '' })
const impactSaving = ref(false)
const impactSaved = ref(false)
const impactError = ref(null)

// Critical blocker rule
const blockerImpactLevels = ref({ HIGH: true, MEDIUM: false, LOW: false })
const blockerDescription = ref('')
const blockerSaving = ref(false)
const blockerSaved = ref(false)
const blockerError = ref(null)

// Readiness thresholds
const thresholds = ref([
  { label: 'NOT_READY',  min: 0,  max: 40 },
  { label: 'AT_RISK',    min: 40, max: 70 },
  { label: 'NEAR_READY', min: 70, max: 90 },
  { label: 'READY',      min: 90, max: 101 },
])
const thresholdSaving = ref(false)
const thresholdSaved = ref(false)
const thresholdError = ref(null)

// Change types
const changeTypes = ref({
  'Code Change':   '',
  'Config Change': '',
  'MDG Workflow':  '',
  'Registration':  '',
})
const changeTypeSaving = ref(false)
const changeTypeSaved = ref(false)
const changeTypeError = ref(null)

// ── Computed ───────────────────────────────────────────────────────────────
const readinessScore = computed(() => status.value?.summary?.readiness_score ?? 0)
const readinessStatus = computed(() => status.value?.summary?.readiness_status ?? 'NOT_READY')
const blockerCount = computed(() => status.value?.summary?.blocker_count ?? status.value?.blockers?.length ?? 0)

const readinessColor = computed(() => {
  const s = readinessStatus.value
  if (s === 'READY') return '#10b981'
  if (s === 'NEAR_READY') return '#f59e0b'
  if (s === 'AT_RISK') return '#f97316'
  return '#ef4444'
})

const scoreConicGradient = computed(() => {
  const score = readinessScore.value
  const color = readinessColor.value
  const pct = Math.min(100, Math.max(0, score))
  return `conic-gradient(${color} 0% ${pct}%, #1e293b ${pct}% 100%)`
})

const blockerCheckedLevels = computed(() => {
  return Object.entries(blockerImpactLevels.value)
    .filter(([, v]) => v)
    .map(([k]) => k)
})

// ── Helpers ────────────────────────────────────────────────────────────────
function flashSaved(savedRef, errorRef) {
  savedRef.value = true
  errorRef.value = null
  setTimeout(() => { savedRef.value = false }, 2000)
}

async function loadStatus() {
  statusLoading.value = true
  try {
    status.value = await fetchSemanticStatus('BE')
  } catch (e) {
    console.error('Failed to load semantic status', e)
  } finally {
    statusLoading.value = false
  }
}

async function loadConfig() {
  configLoading.value = true
  configError.value = null
  try {
    const cfg = await fetchSemanticConfig()
    // Impact levels
    if (cfg.impact_levels) {
      impactLevels.value = { ...cfg.impact_levels }
    }
    // Critical blocker rule
    if (cfg.critical_blocker_rule) {
      const lvls = cfg.critical_blocker_rule.impact_levels ?? []
      blockerImpactLevels.value = {
        HIGH:   lvls.includes('HIGH'),
        MEDIUM: lvls.includes('MEDIUM'),
        LOW:    lvls.includes('LOW'),
      }
      blockerDescription.value = cfg.critical_blocker_rule.description ?? ''
    }
    // Readiness thresholds
    if (cfg.readiness_thresholds && cfg.readiness_thresholds.length) {
      thresholds.value = cfg.readiness_thresholds.map(t => ({ ...t }))
    }
    // Change types
    if (cfg.change_types) {
      changeTypes.value = { ...cfg.change_types }
    }
  } catch (e) {
    configError.value = 'Failed to load configuration'
    console.error(e)
  } finally {
    configLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadStatus()])
})

// ── Save handlers ──────────────────────────────────────────────────────────
async function saveImpactLevels() {
  impactSaving.value = true
  impactError.value = null
  try {
    await updateSemanticConfig({ impact_levels: { ...impactLevels.value } })
    await loadStatus()
    flashSaved(impactSaved, impactError)
  } catch (e) {
    impactError.value = 'Save failed'
    console.error(e)
  } finally {
    impactSaving.value = false
  }
}

async function saveBlockerRule() {
  blockerSaving.value = true
  blockerError.value = null
  try {
    const levels = blockerCheckedLevels.value
    await updateSemanticConfig({
      critical_blocker_rule: {
        impact_levels: levels,
        description: blockerDescription.value,
      }
    })
    await loadStatus()
    flashSaved(blockerSaved, blockerError)
  } catch (e) {
    blockerError.value = 'Save failed'
    console.error(e)
  } finally {
    blockerSaving.value = false
  }
}

async function saveThresholds() {
  thresholdSaving.value = true
  thresholdError.value = null
  try {
    await updateSemanticConfig({
      readiness_thresholds: thresholds.value.map(t => ({
        label: t.label,
        min: Number(t.min),
        max: Number(t.max),
      }))
    })
    await loadStatus()
    flashSaved(thresholdSaved, thresholdError)
  } catch (e) {
    thresholdError.value = 'Save failed'
    console.error(e)
  } finally {
    thresholdSaving.value = false
  }
}

async function saveChangeTypes() {
  changeTypeSaving.value = true
  changeTypeError.value = null
  try {
    await updateSemanticConfig({ change_types: { ...changeTypes.value } })
    await loadStatus()
    flashSaved(changeTypeSaved, changeTypeError)
  } catch (e) {
    changeTypeError.value = 'Save failed'
    console.error(e)
  } finally {
    changeTypeSaving.value = false
  }
}

// ── Impact level badge colors ──────────────────────────────────────────────
const impactBadgeStyle = {
  HIGH:   { background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' },
  MEDIUM: { background: 'rgba(245,158,11,0.15)', color: '#fcd34d', border: '1px solid rgba(245,158,11,0.3)' },
  LOW:    { background: 'rgba(59,130,246,0.15)', color: '#93c5fd', border: '1px solid rgba(59,130,246,0.3)' },
}

const thresholdColors = {
  NOT_READY:  '#ef4444',
  AT_RISK:    '#f97316',
  NEAR_READY: '#f59e0b',
  READY:      '#10b981',
}
</script>

<template>
  <div class="semantic-tab">

    <!-- ── Status Bar ───────────────────────────────────────────────────── -->
    <div class="status-bar">
      <div class="status-bar-inner">
        <!-- Score ring -->
        <div class="score-ring-wrap">
          <div class="score-ring" :style="{ background: scoreConicGradient }">
            <div class="score-ring-inner">
              <span class="score-value" :style="{ color: readinessColor }">{{ readinessScore }}</span>
              <span class="score-pct">%</span>
            </div>
          </div>
        </div>

        <!-- Status info -->
        <div class="status-info">
          <div class="status-label-row">
            <span
              class="status-badge"
              :style="{ background: readinessColor + '22', color: readinessColor, border: `1px solid ${readinessColor}55` }"
            >
              {{ readinessStatus.replace('_', ' ') }}
            </span>
            <span class="status-meta">Compliance Readiness</span>
          </div>
          <div class="status-details">
            <span class="blocker-pill" :class="{ 'blocker-pill--warn': blockerCount > 0 }">
              {{ blockerCount }} critical blocker{{ blockerCount !== 1 ? 's' : '' }}
            </span>
            <span class="status-hint">Based on current semantic layer definitions</span>
          </div>
        </div>

        <!-- Recalculate -->
        <button class="recalc-btn" :disabled="statusLoading" @click="loadStatus">
          <span v-if="statusLoading" class="spin-dot"></span>
          {{ statusLoading ? 'Recalculating...' : 'Recalculate' }}
        </button>
      </div>
    </div>

    <!-- ── Config error ─────────────────────────────────────────────────── -->
    <div v-if="configError" class="global-error">{{ configError }}</div>
    <div v-if="configLoading" class="global-loading">Loading configuration...</div>

    <!-- ── 3 cards row ──────────────────────────────────────────────────── -->
    <div v-if="!configLoading" class="cards-row">

      <!-- Card 1: Impact Levels -->
      <div class="card card--purple">
        <div class="card-header">
          <div class="card-accent" style="background: #8b5cf6"></div>
          <div>
            <div class="card-title">Impact Levels</div>
            <div class="card-subtitle">What each severity level means for go-live</div>
          </div>
        </div>
        <div class="card-body">
          <div v-for="level in ['HIGH', 'MEDIUM', 'LOW']" :key="level" class="impact-row">
            <div class="impact-badge" :style="impactBadgeStyle[level]">{{ level }}</div>
            <textarea
              v-model="impactLevels[level]"
              class="field-textarea"
              rows="2"
              :placeholder="`${level} impact description...`"
            ></textarea>
          </div>
        </div>
        <div class="card-footer">
          <button class="save-btn" :disabled="impactSaving" @click="saveImpactLevels">
            {{ impactSaving ? 'Saving...' : 'Save' }}
          </button>
          <span v-if="impactSaved" class="saved-flash">Saved</span>
          <span v-if="impactError" class="error-flash">{{ impactError }}</span>
        </div>
      </div>

      <!-- Card 2: Critical Blocker Rule -->
      <div class="card card--red">
        <div class="card-header">
          <div class="card-accent" style="background: #ef4444"></div>
          <div>
            <div class="card-title">Critical Blocker Definition</div>
            <div class="card-subtitle">Which obligations are treated as show-stoppers</div>
          </div>
        </div>
        <div class="card-body">
          <div class="field-label">Include as blocker when impact level is:</div>
          <div class="checkbox-group">
            <label v-for="level in ['HIGH', 'MEDIUM', 'LOW']" :key="level" class="checkbox-row">
              <input type="checkbox" v-model="blockerImpactLevels[level]" class="field-checkbox" />
              <span class="impact-badge" :style="impactBadgeStyle[level]">{{ level }}</span>
            </label>
          </div>
          <div class="field-label" style="margin-top: 12px">Description:</div>
          <textarea
            v-model="blockerDescription"
            class="field-textarea"
            rows="3"
            placeholder="Describe what constitutes a critical blocker..."
          ></textarea>
          <div class="blocker-preview">
            Currently: <strong>{{ blockerCheckedLevels.join(', ') || 'none' }}</strong> treated as blockers
            &mdash; <strong :style="{ color: readinessColor }">{{ blockerCount }}</strong> match
          </div>
        </div>
        <div class="card-footer">
          <button class="save-btn" :disabled="blockerSaving" @click="saveBlockerRule">
            {{ blockerSaving ? 'Saving...' : 'Save' }}
          </button>
          <span v-if="blockerSaved" class="saved-flash">Saved</span>
          <span v-if="blockerError" class="error-flash">{{ blockerError }}</span>
        </div>
      </div>

      <!-- Card 3: Readiness Thresholds -->
      <div class="card card--green">
        <div class="card-header">
          <div class="card-accent" style="background: #10b981"></div>
          <div>
            <div class="card-title">Readiness Score Bands</div>
            <div class="card-subtitle">Score ranges that map to status labels</div>
          </div>
        </div>
        <div class="card-body">
          <div
            v-for="(threshold, idx) in thresholds"
            :key="threshold.label"
            class="threshold-row"
          >
            <span
              class="threshold-label"
              :style="{ color: thresholdColors[threshold.label] ?? '#94a3b8' }"
            >{{ threshold.label.replace('_', ' ') }}</span>
            <div class="threshold-range">
              <input
                v-model.number="thresholds[idx].min"
                type="number"
                class="field-number"
                min="0"
                max="100"
              />
              <span class="range-sep">&ndash;</span>
              <input
                v-model.number="thresholds[idx].max"
                type="number"
                class="field-number"
                min="0"
                max="101"
              />
            </div>
          </div>
        </div>
        <div class="card-footer">
          <button class="save-btn" :disabled="thresholdSaving" @click="saveThresholds">
            {{ thresholdSaving ? 'Saving...' : 'Save' }}
          </button>
          <span v-if="thresholdSaved" class="saved-flash">Saved</span>
          <span v-if="thresholdError" class="error-flash">{{ thresholdError }}</span>
        </div>
      </div>

    </div>

    <!-- ── Change Type Glossary (full width) ────────────────────────────── -->
    <div v-if="!configLoading" class="card card--blue card--full">
      <div class="card-header">
        <div class="card-accent" style="background: #3b82f6"></div>
        <div>
          <div class="card-title">Change Type Definitions</div>
          <div class="card-subtitle">What each change category means for delivery teams</div>
        </div>
      </div>
      <div class="card-body change-types-grid">
        <div
          v-for="(description, type) in changeTypes"
          :key="type"
          class="change-type-row"
        >
          <span class="change-type-label">{{ type }}</span>
          <input
            v-model="changeTypes[type]"
            type="text"
            class="field-input"
            :placeholder="`Definition for ${type}...`"
          />
        </div>
      </div>
      <div class="card-footer">
        <button class="save-btn" :disabled="changeTypeSaving" @click="saveChangeTypes">
          {{ changeTypeSaving ? 'Saving...' : 'Save' }}
        </button>
        <span v-if="changeTypeSaved" class="saved-flash">Saved</span>
        <span v-if="changeTypeError" class="error-flash">{{ changeTypeError }}</span>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ── Tab container ─────────────────────────────────────────────────────── */
.semantic-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.semantic-tab::-webkit-scrollbar { width: 5px; }
.semantic-tab::-webkit-scrollbar-track { background: #0f172a; }
.semantic-tab::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

/* ── Global states ────────────────────────────────────────────────────── */
.global-loading {
  font-size: 13px;
  color: #64748b;
  padding: 8px 0;
}

.global-error {
  font-size: 13px;
  color: #f87171;
  padding: 8px 12px;
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 6px;
}

/* ── Status bar ───────────────────────────────────────────────────────── */
.status-bar {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px 20px;
  flex-shrink: 0;
}

.status-bar-inner {
  display: flex;
  align-items: center;
  gap: 20px;
}

/* Score ring */
.score-ring-wrap {
  flex-shrink: 0;
}

.score-ring {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5px;
}

.score-ring-inner {
  width: 100%;
  height: 100%;
  background: #0f172a;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1px;
}

.score-value {
  font-size: 18px;
  font-weight: 800;
  line-height: 1;
}

.score-pct {
  font-size: 10px;
  color: #64748b;
  align-self: flex-end;
  padding-bottom: 2px;
}

/* Status info */
.status-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-label-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 3px 10px;
  border-radius: 999px;
  text-transform: uppercase;
}

.status-meta {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.status-details {
  display: flex;
  align-items: center;
  gap: 12px;
}

.blocker-pill {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(100,116,139,0.2);
  color: #94a3b8;
  border: 1px solid #334155;
  font-weight: 600;
}

.blocker-pill--warn {
  background: rgba(239,68,68,0.1);
  color: #f87171;
  border-color: rgba(239,68,68,0.3);
}

.status-hint {
  font-size: 11px;
  color: #64748b;
}

/* Recalculate button */
.recalc-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: transparent;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  letter-spacing: 0.02em;
}

.recalc-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #93c5fd;
  background: rgba(59,130,246,0.08);
}

.recalc-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.spin-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid #94a3b8;
  border-top-color: transparent;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── 3-card row ───────────────────────────────────────────────────────── */
.cards-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  flex-shrink: 0;
}

/* ── Card base ────────────────────────────────────────────────────────── */
.card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card--full {
  flex-shrink: 0;
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}

.card-accent {
  width: 3px;
  height: 32px;
  border-radius: 2px;
  flex-shrink: 0;
  margin-top: 2px;
}

.card-title {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 2px;
  letter-spacing: 0.01em;
}

.card-subtitle {
  font-size: 11px;
  color: #64748b;
}

.card-body {
  flex: 1;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-footer {
  padding: 10px 16px;
  border-top: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* ── Form fields ──────────────────────────────────────────────────────── */
.field-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.field-textarea {
  width: 100%;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #e2e8f0;
  font-size: 12px;
  font-family: inherit;
  padding: 8px 10px;
  resize: vertical;
  line-height: 1.5;
  transition: border-color 0.15s;
}

.field-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.field-textarea::placeholder {
  color: #475569;
}

.field-input {
  flex: 1;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #e2e8f0;
  font-size: 12px;
  font-family: inherit;
  padding: 7px 10px;
  transition: border-color 0.15s;
}

.field-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.field-input::placeholder {
  color: #475569;
}

.field-number {
  width: 60px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #e2e8f0;
  font-size: 12px;
  font-family: inherit;
  padding: 5px 8px;
  text-align: center;
  transition: border-color 0.15s;
}

.field-number:focus {
  outline: none;
  border-color: #3b82f6;
}

.field-checkbox {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: #3b82f6;
  flex-shrink: 0;
}

/* ── Save button + flash ────────────────────────────────────────────────── */
.save-btn {
  padding: 5px 14px;
  background: #3b82f6;
  border: none;
  border-radius: 5px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  letter-spacing: 0.02em;
}

.save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.save-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.saved-flash {
  font-size: 12px;
  color: #4ade80;
  font-weight: 600;
  animation: fadeInOut 2s ease forwards;
}

.error-flash {
  font-size: 12px;
  color: #f87171;
  font-weight: 500;
}

@keyframes fadeInOut {
  0%   { opacity: 0; transform: translateY(2px); }
  15%  { opacity: 1; transform: translateY(0); }
  75%  { opacity: 1; }
  100% { opacity: 0; }
}

/* ── Impact level rows ───────────────────────────────────────────────── */
.impact-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.impact-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  align-self: flex-start;
  white-space: nowrap;
}

/* ── Checkbox group ──────────────────────────────────────────────────── */
.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

/* ── Blocker preview ────────────────────────────────────────────────── */
.blocker-preview {
  font-size: 11px;
  color: #64748b;
  padding: 8px 10px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  line-height: 1.6;
}

.blocker-preview strong {
  color: #94a3b8;
}

/* ── Threshold rows ─────────────────────────────────────────────────── */
.threshold-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid #1e293b;
}

.threshold-row:last-child {
  border-bottom: none;
}

.threshold-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  min-width: 90px;
}

.threshold-range {
  display: flex;
  align-items: center;
  gap: 6px;
}

.range-sep {
  font-size: 12px;
  color: #475569;
}

/* ── Change types grid ───────────────────────────────────────────────── */
.change-types-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.change-type-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.change-type-label {
  font-size: 11px;
  font-weight: 700;
  color: #93c5fd;
  letter-spacing: 0.03em;
}
</style>
