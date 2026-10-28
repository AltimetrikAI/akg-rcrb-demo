<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchProcessSteps } from '../api.js'

const props = defineProps({ assessmentCompleted: { type: Boolean, default: false } })

const O2C_STAGES = [
  { id: 'order',      label: 'Sales Order',       subtitle: 'Customer order intake & ERP entry',            color: '#64748b' },
  { id: 'invoice',    label: 'Invoice Creation',   subtitle: 'Billing document generated in SAP S/4HANA',   color: '#3b82f6' },
  { id: 'vat',        label: 'VAT Determination',  subtitle: 'Tax calculation & VIES B2B validation',        color: '#10b981' },
  { id: 'peppol',     label: 'Peppol Formatting',  subtitle: 'UBL 2.1 XML structure & field mapping',        color: '#8b5cf6' },
  { id: 'delivery',   label: 'Network Delivery',   subtitle: 'AS4 Peppol transmission to buyer',             color: '#06b6d4' },
  { id: 'settlement', label: 'AR Settlement',      subtitle: 'Payment receipt & receivables reconciliation', color: '#64748b' },
]

const steps = ref([])
const loading = ref(false)
const error = ref(null)
const activeStageId = ref(null)

function mapToStage(step) {
  const hay = ((step.name || '') + ' ' + (step.source_file || '')).toLowerCase()
  if (/vat|tax|tax_det/.test(hay)) return 'vat'
  if (/peppol|ubl|_output/.test(hay)) return 'peppol'
  if (/deliver|router|send/.test(hay)) return 'delivery'
  if (/invoice|billing|create/.test(hay)) return 'invoice'
  if (/order|sales/.test(hay)) return 'order'
  if (/payment|ar|settl|cash/.test(hay)) return 'settlement'
  return 'invoice'
}

const stageSteps = computed(() => {
  const map = {}
  O2C_STAGES.forEach(s => { map[s.id] = [] })
  steps.value.forEach(step => {
    const sid = mapToStage(step)
    if (map[sid]) map[sid].push(step)
  })
  Object.keys(map).forEach(sid => {
    map[sid].sort((a, b) => {
      const ac = a.change_required ? 0 : 1
      const bc = b.change_required ? 0 : 1
      return ac - bc
    })
  })
  return map
})

const activeStage = computed(() => O2C_STAGES.find(s => s.id === activeStageId.value) || null)

const activeSteps = computed(() => {
  if (!activeStageId.value) return []
  return stageSteps.value[activeStageId.value] || []
})

const activeChangedCount = computed(() => props.assessmentCompleted ? activeSteps.value.filter(s => s.change_required).length : 0)

function stageCount(stageId) {
  return (stageSteps.value[stageId] || []).length
}

function stageHasChange(stageId) {
  return props.assessmentCompleted && (stageSteps.value[stageId] || []).some(s => s.change_required)
}

function selectStage(stageId) {
  activeStageId.value = stageId
}

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchProcessSteps()
    steps.value = Array.isArray(data) ? data : []
    const firstChanged = O2C_STAGES.find(s => (stageSteps.value[s.id] || []).some(st => st.change_required))
    activeStageId.value = props.assessmentCompleted && firstChanged ? firstChanged.id : 'invoice'
  } catch (e) {
    error.value = 'Failed to load process flow data'
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())

const PEPPOL_FIELDS = {
  'BT-1':   { name: 'Invoice Number',              desc: 'Unique invoice identifier assigned by the seller — must be sequential and non-repeating per Royal Decree.' },
  'BT-2':   { name: 'Invoice Issue Date',           desc: 'Date the invoice was created. Required in ISO 8601 format (YYYY-MM-DD).' },
  'BT-5':   { name: 'Invoice Currency Code',        desc: 'Currency for all monetary amounts. Belgium B2B invoices must use EUR.' },
  'BT-9':   { name: 'Payment Due Date',             desc: 'Date by which full payment must be received. Required for Belgian B2B under Late Payment Directive.' },
  'BT-24':  { name: 'Specification Identifier',     desc: 'Must be set to the Peppol BIS 3.0 URI — confirms the invoice conforms to the EN 16931 European standard.' },
  'BT-031': { name: 'Seller VAT Number',            desc: 'BE VAT number of the invoicing entity (format: BE + 10 digits). Mandatory for all Belgian B2B transactions.' },
  'BT-048': { name: 'Buyer VAT Number',             desc: 'Belgian buyer\'s VAT number. Must be validated against VIES before invoice submission to confirm B2B status.' },
  'BT-116': { name: 'VAT Taxable Amount',           desc: 'Net amount subject to VAT for this rate group. Required per VAT rate line (BG-23) — Belgium applies 0%, 6%, 12%, 21%.' },
  'BT-117': { name: 'VAT Tax Amount',               desc: 'Calculated tax amount for this VAT rate. Must match BT-116 × BT-119 exactly — discrepancies cause rejection.' },
  'BT-119': { name: 'VAT Rate (%)',                 desc: 'VAT percentage applied to this line group. Belgian rates: 21% standard, 12% reduced, 6% super-reduced, 0% exempt.' },
  'BT-128': { name: 'Invoice Object Reference',     desc: 'Structured reference linking the invoice to a contract, purchase order, or project. Required for Belgian public-sector buyers.' },
  'BG-23':  { name: 'VAT Breakdown Group',          desc: 'One BG-23 block is required for each distinct VAT rate on the invoice. Groups taxable amount, tax amount, and rate together.' },
  'BG-3':   { name: 'Preceding Invoice Reference',  desc: 'Links a credit or debit note back to the original invoice. Required when issuing corrections under Belgian e-invoicing rules.' },
  'BT-81':  { name: 'Payment Means Type Code',      desc: 'Coded identifier for the payment method (e.g. 58 = SEPA Credit Transfer). Required for straight-through payment processing.' },
  'BT-84':  { name: 'Payment Account (IBAN)',       desc: 'IBAN of the seller\'s bank account. Required when payment means is SEPA Credit Transfer (BT-81 = 58).' },
  'BT-86':  { name: 'Payment Service Provider (BIC)', desc: 'BIC/SWIFT code of the seller\'s bank. Required alongside BT-84 for cross-border SEPA payments.' },
}

function fieldInfo(code) {
  return PEPPOL_FIELDS[code] || { name: code, desc: 'Peppol BIS 3.0 mandatory field — refer to EN 16931 specification.' }
}
</script>

<template>
  <div class="o2c-root">
    <div class="o2c-header">
      <div class="o2c-header-titles">
        <span class="o2c-title">Order-to-Cash Process Flow</span>
        <span class="o2c-dot">·</span>
        <span class="o2c-subtitle">Regulatory Compliance — Process Change Impact</span>
      </div>
    </div>

    <div v-if="loading" class="o2c-state">Loading Order-to-Cash flow...</div>
    <div v-else-if="error" class="o2c-state o2c-state--error">{{ error }}</div>

    <template v-else>
      <div class="pipeline-row">
        <template v-for="(stage, idx) in O2C_STAGES" :key="stage.id">
          <button
            class="stage-pill"
            :class="{ 'stage-pill--active': activeStageId === stage.id }"
            :style="activeStageId === stage.id ? { borderColor: stage.color, boxShadow: `0 0 0 1px ${stage.color}22` } : {}"
            @click="selectStage(stage.id)"
          >
            <span class="pill-num" :style="activeStageId === stage.id ? { color: stage.color } : {}">{{ idx + 1 }}</span>
            <span class="pill-label">{{ stage.label }}</span>
            <span v-if="stageCount(stage.id) > 0" class="pill-count" :style="activeStageId === stage.id ? { background: stage.color + '22', color: stage.color, borderColor: stage.color + '55' } : {}">
              {{ stageCount(stage.id) }}
            </span>
            <span v-if="stageHasChange(stage.id)" class="pill-alert"></span>
          </button>
          <span v-if="idx < O2C_STAGES.length - 1" class="pipeline-arrow">&#8594;</span>
        </template>
      </div>

      <div v-if="activeStage" class="detail-panel">
        <div class="detail-header">
          <div class="detail-header-left">
            <span class="detail-stage-dot" :style="{ background: activeStage.color }"></span>
            <span class="detail-stage-label">{{ activeStage.label.toUpperCase() }}</span>
          </div>
          <div class="detail-stage-subtitle">{{ activeStage.subtitle }}</div>
          <div class="detail-counts">
            {{ activeSteps.length }} step{{ activeSteps.length !== 1 ? 's' : '' }}
            <template v-if="activeChangedCount > 0">
              <span class="detail-counts-sep">—</span>
              <span class="detail-counts-changed">{{ activeChangedCount }} require{{ activeChangedCount === 1 ? 's' : '' }} changes</span>
            </template>
          </div>
        </div>

        <div class="detail-body">
          <div v-if="activeSteps.length === 0" class="empty-stage">
            No implementation steps mapped to this stage
          </div>

          <div
            v-for="step in activeSteps"
            :key="step.id"
            class="step-card"
            :class="{ 'step-card--changed': assessmentCompleted && step.change_required }"
          >
            <div class="step-card-inner">
              <div class="step-top-row">
                <div class="step-name-group">
                  <span class="step-name">{{ step.name }}</span>
                  <span
                    class="step-type"
                    :style="step.change_required ? { color: '#94a3b8' } : {}"
                  >{{ step.type }}</span>
                </div>
                <div class="step-badges-right">
                  <span
                    v-if="step.language"
                    class="lang-badge"
                    :class="step.language === 'ABAP' ? 'lang-badge--abap' : step.language === 'Java' ? 'lang-badge--java' : 'lang-badge--other'"
                  >{{ step.language }}</span>
                  <span v-if="assessmentCompleted && step.change_required" class="change-required-badge">CHANGE REQUIRED</span>
                </div>
              </div>

              <div v-if="assessmentCompleted && step.change_required" class="step-rationale">
                Royal Decree 9 March 2022 — mandatory Peppol BIS 3.0 fields must be populated before transmission via AS4.
              </div>

              <div v-if="assessmentCompleted && step.change_required && step.peppol_fields && step.peppol_fields.length" class="step-peppol-section">
                <div class="peppol-section-title">Fields to add / populate</div>
                <div v-for="field in step.peppol_fields" :key="field" class="peppol-field-row">
                  <div class="peppol-field-header">
                    <span class="bt-code">{{ field }}</span>
                    <span class="bt-name">{{ fieldInfo(field).name }}</span>
                  </div>
                  <div class="bt-desc">{{ fieldInfo(field).desc }}</div>
                </div>
              </div>

              <div v-if="step.source_file" class="step-source">{{ step.source_file }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.o2c-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f172a;
  overflow: hidden;
}

.o2c-header {
  display: flex;
  align-items: center;
  padding: 14px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}

.o2c-header-titles {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.o2c-title {
  font-size: 14px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.01em;
}

.o2c-dot {
  color: #475569;
  font-size: 14px;
}

.o2c-subtitle {
  font-size: 13px;
  color: #64748b;
}

.o2c-state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  font-size: 13px;
  color: #64748b;
}

.o2c-state--error {
  color: #f87171;
}

.pipeline-row {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 16px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  overflow-x: auto;
  flex-wrap: nowrap;
}

.pipeline-row::-webkit-scrollbar {
  height: 4px;
}
.pipeline-row::-webkit-scrollbar-track { background: #0f172a; }
.pipeline-row::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

.stage-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s, background 0.15s;
  position: relative;
  flex-shrink: 0;
}

.stage-pill:hover {
  background: #1e293b;
  border-color: #475569;
}

.stage-pill--active {
  background: #0f172a;
}

.pill-num {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.pill-label {
  font-size: 12px;
  font-weight: 600;
  color: #cbd5e1;
}

.stage-pill--active .pill-label {
  color: #f1f5f9;
}

.pill-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.pill-alert {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ef4444;
  flex-shrink: 0;
}

.pipeline-arrow {
  font-size: 16px;
  color: #334155;
  padding: 0 6px;
  flex-shrink: 0;
  user-select: none;
}

.detail-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.detail-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.detail-stage-label {
  font-size: 11px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.08em;
}

.detail-stage-subtitle {
  font-size: 12px;
  color: #64748b;
  flex: 1;
}

.detail-counts {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.detail-counts-sep {
  color: #475569;
}

.detail-counts-changed {
  color: #f87171;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-body::-webkit-scrollbar {
  width: 6px;
}
.detail-body::-webkit-scrollbar-track { background: #0f172a; }
.detail-body::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

.empty-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  font-size: 13px;
  color: #475569;
  text-align: center;
}

.step-card {
  border: 1px solid #334155;
  border-left: 4px solid #334155;
  border-radius: 6px;
  background: #1e293b;
  transition: border-color 0.15s;
  opacity: 1;
}

.step-card:not(.step-card--changed) {
  opacity: 0.7;
}

.step-card--changed {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.06);
  border-color: rgba(239, 68, 68, 0.25);
  border-left-color: #ef4444;
}

.step-card-inner {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-top-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.step-name-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.step-name {
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
  word-break: break-all;
  line-height: 1.35;
}

.step-type {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #475569;
}

.step-badges-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.lang-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.lang-badge--abap {
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34d399;
}

.lang-badge--java {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: #60a5fa;
}

.lang-badge--other {
  background: rgba(100, 116, 139, 0.12);
  border: 1px solid rgba(100, 116, 139, 0.4);
  color: #94a3b8;
}

.change-required-badge {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.5);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  color: #f87171;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.step-rationale {
  font-size: 11px;
  color: #f59e0b;
  line-height: 1.5;
  padding: 6px 10px;
  background: rgba(245, 158, 11, 0.07);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 4px;
}

.step-peppol-section {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 5px;
  overflow: hidden;
}

.peppol-section-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #7c3aed;
  background: rgba(139, 92, 246, 0.1);
  padding: 5px 10px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.2);
}

.peppol-field-row {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.peppol-field-row:last-child {
  border-bottom: none;
}

.peppol-field-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.bt-code {
  font-size: 10px;
  font-weight: 800;
  font-family: monospace;
  color: #a78bfa;
  background: rgba(139, 92, 246, 0.15);
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 3px;
  padding: 1px 6px;
  flex-shrink: 0;
}

.bt-name {
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
}

.bt-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.5;
  padding-left: 2px;
}

.step-source {
  font-size: 10px;
  color: #475569;
  word-break: break-all;
  border-top: 1px solid #334155;
  padding-top: 8px;
  font-family: monospace;
  line-height: 1.4;
}

.step-card--changed .step-source {
  border-top-color: rgba(239, 68, 68, 0.15);
}
</style>
