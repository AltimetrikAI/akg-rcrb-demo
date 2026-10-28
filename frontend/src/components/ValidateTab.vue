<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  fetchValidationGraph,
  updateNodeValidation,
  addRelationship,
  removeRelationship,
} from '../api.js'

// ── Constants ─────────────────────────────────────────────────────────────
const STATUS_COLORS = {
  unreviewed:          '#475569',
  confirmed:           '#10b981',
  incorrect:           '#ef4444',
  needs_clarification: '#f59e0b',
}

const SYSTEMS = [
  // ABAP
  { file: 'Z_HPE_INVOICE_CREATE.abap',  label: 'Invoice Create',        lang: 'ABAP' },
  { file: 'Z_HPE_VATCHECK.abap',        label: 'VAT Check',             lang: 'ABAP' },
  { file: 'Z_HPE_PEPPOL_OUTPUT.abap',   label: 'Peppol Output',         lang: 'ABAP' },
  { file: 'Z_HPE_FI_TAXPOST.abap',      label: 'FI Tax Post',           lang: 'ABAP' },
  // Java
  { file: 'InvoiceDeliveryService.java', label: 'Invoice Delivery',      lang: 'Java' },
  { file: 'PeppolRouter.java',           label: 'Peppol Router',         lang: 'Java' },
  { file: 'CustomerVatService.java',     label: 'Customer VAT',          lang: 'Java' },
  { file: 'TaxDeterminationService.java',label: 'Tax Determination',     lang: 'Java' },
  { file: 'BelgianVatValidator.java',    label: 'Belgian VAT Validator', lang: 'Java' },
]

// ── State ─────────────────────────────────────────────────────────────────
const loading          = ref(true)
const loadError        = ref(null)
const allNodes         = ref([])
const allEdges         = ref([])
const selectedSystemFile = ref(null)
const selectedNodeId   = ref(null)

const form = ref({
  validated_status: '',
  change_required:  false,
  peppol_fields:    [],
  validation_notes: '',
})

const saving      = ref(false)
const saveSuccess = ref(false)
const saveError   = ref(null)

const queueVisible = ref(true)

const newFieldInput  = ref('')
const addCallInput   = ref('')
const showDropdown   = ref(false)
const addCallLoading = ref(false)
const addCallError   = ref(null)

// ── Computed ──────────────────────────────────────────────────────────────
const selectedNode = computed(() =>
  selectedNodeId.value
    ? allNodes.value.find(n => n.id === selectedNodeId.value) ?? null
    : null
)

const reviewedNodes     = computed(() => allNodes.value.filter(n => n.validated_status !== 'unreviewed'))
const confirmedNodes    = computed(() => allNodes.value.filter(n => n.validated_status === 'confirmed'))
const incorrectNodes    = computed(() => allNodes.value.filter(n => n.validated_status === 'incorrect'))
const needsClarifyNodes = computed(() => allNodes.value.filter(n => n.validated_status === 'needs_clarification'))
const progressPct       = computed(() =>
  allNodes.value.length ? (reviewedNodes.value.length / allNodes.value.length) * 100 : 0
)

const confidenceColor = computed(() => {
  const pct = progressPct.value
  if (pct <= 30) return '#ef4444'
  if (pct <= 70) return '#f59e0b'
  return '#10b981'
})

const validationQueue = computed(() => {
  const priority1 = allNodes.value.filter(n => n.change_required === true  && n.validated_status === 'unreviewed')
  const priority2 = allNodes.value.filter(n => n.change_required === true  && n.validated_status === 'needs_clarification')
  const priority3 = allNodes.value.filter(n => n.change_required === false && n.validated_status === 'unreviewed')
  return [...priority1, ...priority2, ...priority3].slice(0, 5).map(node => ({
    ...node,
    systemLabel: SYSTEMS.find(s => s.file === node.source_file)?.label ?? node.source_file ?? 'Unknown',
  }))
})

// Map source_file -> node[]
const nodesBySystem = computed(() => {
  const map = new Map()
  for (const node of allNodes.value) {
    const key = node.source_file ?? '__other__'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(node)
  }
  return map
})

// Systems list enriched with live counts
const systemsWithCounts = computed(() => {
  const knownFiles = new Set(SYSTEMS.map(s => s.file))
  const result = SYSTEMS.map(s => {
    const nodes     = nodesBySystem.value.get(s.file) ?? []
    const total     = nodes.length
    const reviewed  = nodes.filter(n => n.validated_status !== 'unreviewed').length
    const changed   = nodes.filter(n => n.change_required).length
    const confirmed = nodes.filter(n => n.validated_status === 'confirmed').length
    return { ...s, nodes, total, reviewed, changed, confirmed }
  })

  // Fallback "Other" group for nodes whose source_file is not in SYSTEMS
  const otherNodes = allNodes.value.filter(n => !knownFiles.has(n.source_file ?? ''))
  if (otherNodes.length > 0) {
    result.push({
      file:      '__other__',
      label:     'Other',
      lang:      '',
      nodes:     otherNodes,
      total:     otherNodes.length,
      reviewed:  otherNodes.filter(n => n.validated_status !== 'unreviewed').length,
      changed:   otherNodes.filter(n => n.change_required).length,
      confirmed: otherNodes.filter(n => n.validated_status === 'confirmed').length,
    })
  }
  return result
})

// Nodes for the selected system: change_required first, then alphabetical by name
const selectedSystemNodes = computed(() => {
  if (!selectedSystemFile.value) return []
  const nodes = nodesBySystem.value.get(selectedSystemFile.value) ?? []
  return [...nodes].sort((a, b) => {
    if (a.change_required && !b.change_required) return -1
    if (!a.change_required && b.change_required) return 1
    return (a.name ?? '').localeCompare(b.name ?? '')
  })
})

const outgoingEdges = computed(() =>
  selectedNodeId.value
    ? allEdges.value.filter(e => e.from_id === selectedNodeId.value && e.label === 'CALLS')
    : []
)

const addCallSuggestions = computed(() => {
  const q = addCallInput.value.trim().toLowerCase()
  if (!q) return []
  const existingTargets = new Set(outgoingEdges.value.map(e => e.to_id))
  return allNodes.value
    .filter(n =>
      n.id !== selectedNodeId.value &&
      !existingTargets.has(n.id) &&
      n.name.toLowerCase().includes(q)
    )
    .slice(0, 8)
})

// ── Helpers ───────────────────────────────────────────────────────────────
function getStatusColor(status) {
  return STATUS_COLORS[status] ?? STATUS_COLORS.unreviewed
}

function getStatusLabel(status) {
  const LABELS = {
    unreviewed:          'UNREVIEWED',
    confirmed:           'CONFIRMED',
    incorrect:           'INCORRECT',
    needs_clarification: 'NEEDS CLARITY',
  }
  return LABELS[status] ?? String(status).toUpperCase()
}

function getProgressPct(sys) {
  return sys.total ? (sys.reviewed / sys.total) * 100 : 0
}

// ── System selection ──────────────────────────────────────────────────────
function selectSystem(file) {
  if (selectedSystemFile.value === file) {
    selectedSystemFile.value = null
  } else {
    selectedSystemFile.value = file
  }
  selectedNodeId.value = null
}

function selectNode(nodeId) {
  selectedNodeId.value = nodeId
}

function handleQueueCardClick(node) {
  selectedSystemFile.value = node.source_file
  selectedNodeId.value     = node.id
}

// ── Load data ─────────────────────────────────────────────────────────────
async function loadData() {
  loading.value   = true
  loadError.value = null
  try {
    const data     = await fetchValidationGraph()
    allNodes.value = data.nodes ?? []
    allEdges.value = (data.edges ?? []).filter(e => e.label === 'CALLS')
  } catch (e) {
    loadError.value = 'Failed to load validation graph'
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ── Watch selected node → reset form ─────────────────────────────────────
watch(selectedNode, node => {
  saveSuccess.value   = false
  saveError.value     = null
  addCallInput.value  = ''
  addCallError.value  = null
  showDropdown.value  = false
  newFieldInput.value = ''

  if (!node) {
    form.value = { validated_status: '', change_required: false, peppol_fields: [], validation_notes: '' }
    return
  }
  form.value = {
    validated_status: node.validated_status ?? 'unreviewed',
    change_required:  !!node.change_required,
    peppol_fields:    Array.isArray(node.peppol_fields) ? [...node.peppol_fields] : [],
    validation_notes: node.validation_notes ?? '',
  }
})

// ── Peppol fields ─────────────────────────────────────────────────────────
function addPeppolField() {
  const val = newFieldInput.value.trim().toUpperCase()
  if (!val || form.value.peppol_fields.includes(val)) {
    newFieldInput.value = ''
    return
  }
  form.value.peppol_fields.push(val)
  newFieldInput.value = ''
}

function removePeppolField(field) {
  form.value.peppol_fields = form.value.peppol_fields.filter(f => f !== field)
}

// ── CALLS edge management ─────────────────────────────────────────────────
function onAddCallInput() {
  showDropdown.value = addCallInput.value.trim().length > 0
}

function hideDropdown() {
  setTimeout(() => { showDropdown.value = false }, 150)
}

function selectAddCallTarget(node) {
  addCallInput.value = node.name
  showDropdown.value = false
  doAddCall(node)
}

async function doAddCall(targetNode) {
  if (!selectedNode.value || !targetNode) return
  addCallLoading.value = true
  addCallError.value   = null
  try {
    await addRelationship(selectedNode.value.id, targetNode.id, 'CALLS')
    const newEdge = {
      id:      `${selectedNode.value.id}__${targetNode.id}__CALLS`,
      from_id: selectedNode.value.id,
      to_id:   targetNode.id,
      label:   'CALLS',
    }
    allEdges.value.push(newEdge)
    addCallInput.value = ''
    showDropdown.value = false
  } catch (e) {
    addCallError.value = 'Failed to add relationship'
    console.error(e)
  } finally {
    addCallLoading.value = false
  }
}

async function onAddCallClick() {
  const q = addCallInput.value.trim()
  if (!q) return
  const match =
    allNodes.value.find(n => n.name.toLowerCase() === q.toLowerCase()) ??
    addCallSuggestions.value[0] ??
    null
  if (match) {
    await doAddCall(match)
  } else {
    addCallError.value = 'No matching node found'
  }
}

async function doRemoveCall(edge) {
  if (!selectedNode.value) return
  try {
    await removeRelationship(selectedNode.value.id, edge.to_id, 'CALLS')
    allEdges.value = allEdges.value.filter(e => e.id !== edge.id)
  } catch (e) {
    console.error('Failed to remove relationship', e)
  }
}

// ── Save ──────────────────────────────────────────────────────────────────
async function save() {
  if (!selectedNode.value || saving.value) return
  saving.value      = true
  saveSuccess.value = false
  saveError.value   = null
  try {
    await updateNodeValidation(selectedNode.value.id, {
      validated_status: form.value.validated_status,
      change_required:  form.value.change_required,
      peppol_fields:    form.value.peppol_fields,
      validation_notes: form.value.validation_notes,
    })
    const idx = allNodes.value.findIndex(n => n.id === selectedNode.value.id)
    if (idx !== -1) {
      allNodes.value[idx] = {
        ...allNodes.value[idx],
        validated_status: form.value.validated_status,
        change_required:  form.value.change_required,
        peppol_fields:    [...form.value.peppol_fields],
        validation_notes: form.value.validation_notes,
      }
    }
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 2000)
  } catch (e) {
    saveError.value = 'Save failed — ' + e.message
    console.error(e)
  } finally {
    saving.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────
onMounted(() => loadData())
</script>

<template>
  <div class="validate-root">

    <!-- HEADER ──────────────────────────────────────────────────────────── -->
    <div class="vt-header">
      <div class="vt-header-left">
        <span class="vt-title">Human-in-the-Loop Validation</span>
        <span class="vt-sep">·</span>
        <span class="vt-subtitle">Process KG</span>
      </div>
      <div class="vt-header-center">
        <div class="progress-wrap">
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
          </div>
          <span class="progress-label">
            {{ reviewedNodes.length }} / {{ allNodes.length }} reviewed
          </span>
        </div>
        <div class="progress-stats">
          <span class="pstat pstat--confirmed">{{ confirmedNodes.length }} confirmed</span>
          <span class="pstat-sep">·</span>
          <span class="pstat pstat--incorrect">{{ incorrectNodes.length }} incorrect</span>
          <span class="pstat-sep">·</span>
          <span class="pstat pstat--unclear">{{ needsClarifyNodes.length }} unclear</span>
        </div>
      </div>
      <div class="vt-header-right">
        <span class="confidence-score" :style="{ color: confidenceColor }">{{ Math.round(progressPct) }}%</span>
        <span class="confidence-label">KG Confidence</span>
        <span class="confidence-detail">{{ reviewedNodes.length }} of {{ allNodes.length }} nodes human-validated</span>
      </div>
    </div>

    <!-- LOADING / ERROR ──────────────────────────────────────────────────── -->
    <div v-if="loading" class="vt-state">Loading validation data...</div>
    <div v-else-if="loadError" class="vt-state vt-state--error">{{ loadError }}</div>

    <!-- VALIDATION QUEUE ────────────────────────────────────────────── -->
    <div v-if="!loading && !loadError" class="queue-strip">
        <div class="queue-header-row">
          <div class="queue-header-left">
            <span class="queue-title">VALIDATION QUEUE</span>
            <span v-if="validationQueue.length > 0" class="queue-badge">{{ validationQueue.length }} items need attention</span>
          </div>
          <button class="queue-toggle-btn" @click="queueVisible = !queueVisible">
            {{ queueVisible ? 'Hide' : 'Show' }}
            <span class="queue-toggle-arrow">{{ queueVisible ? '▲' : '▼' }}</span>
          </button>
        </div>
        <div v-if="queueVisible" class="queue-cards-row">
          <div v-if="validationQueue.length === 0" class="queue-all-clear">
            All critical nodes have been reviewed
          </div>
          <div
            v-else
            v-for="item in validationQueue"
            :key="item.id"
            class="queue-card"
            @click="handleQueueCardClick(item)"
          >
            <span
              class="qc-status-badge"
              :style="{ background: getStatusColor(item.validated_status) }"
            >{{ getStatusLabel(item.validated_status) }}</span>
            <div class="qc-system">{{ item.systemLabel }}</div>
            <div class="qc-name">{{ item.name }}</div>
            <div :class="item.change_required ? 'qc-change qc-change--required' : 'qc-change qc-change--none'">
              {{ item.change_required ? 'change required' : 'no change needed' }}
            </div>
          </div>
        </div>
    </div>

    <!-- SYSTEM GRID + BODY ───────────────────────────────────────────────── -->
    <template v-if="!loading && !loadError">

      <!-- SYSTEM GRID ──────────────────────────────────────────────────── -->
      <div class="system-grid">
        <button
          v-for="sys in systemsWithCounts"
          :key="sys.file"
          class="system-card"
          :class="{ 'system-card--active': selectedSystemFile === sys.file }"
          @click="selectSystem(sys.file)"
        >
          <div class="sc-top">
            <span class="sc-label">{{ sys.label }}</span>
            <span
              v-if="sys.lang"
              class="sc-lang-badge"
              :class="sys.lang === 'ABAP' ? 'sc-lang--abap' : 'sc-lang--java'"
            >{{ sys.lang }}</span>
          </div>
          <div v-if="sys.lang" class="sc-file">{{ sys.lang === 'ABAP' ? 'SAP ABAP' : 'Java Microservice' }}</div>
          <div v-else class="sc-file">Unclassified</div>
          <div class="sc-progress-track">
            <div
              class="sc-progress-fill"
              :style="{ width: getProgressPct(sys) + '%' }"
            ></div>
          </div>
          <div class="sc-counts">
            <span class="sc-count">{{ sys.total }} total</span>
            <span class="sc-count-sep">·</span>
            <span class="sc-count sc-count--changed">{{ sys.changed }} changed</span>
            <span class="sc-count-sep">·</span>
            <span class="sc-count sc-count--confirmed">{{ sys.confirmed }} confirmed</span>
          </div>
        </button>
      </div>

      <!-- BODY ────────────────────────────────────────────────────────────── -->
      <div class="vt-body">

        <!-- LEFT: function list ──────────────────────────────────────────── -->
        <div class="vt-left">
          <div v-if="!selectedSystemFile" class="fn-empty">
            Select a system above to view its functions
          </div>
          <div v-else class="fn-list">
            <button
              v-for="node in selectedSystemNodes"
              :key="node.id"
              class="fn-row"
              :class="{
                'fn-row--selected': selectedNodeId === node.id,
                'fn-row--changed':  node.change_required,
              }"
              @click="selectNode(node.id)"
            >
              <span class="fn-name">{{ node.name }}</span>
              <span v-if="node.label" class="fn-type-pill">{{ node.label }}</span>
              <span v-if="node.change_required" class="change-badge">!</span>
              <span
                class="status-dot"
                :style="{ background: getStatusColor(node.validated_status) }"
              ></span>
            </button>
          </div>
        </div>

        <!-- RIGHT: validation panel ─────────────────────────────────────── -->
        <div class="vt-right">

          <!-- Empty state -->
          <div v-if="!selectedNode" class="vt-empty">
            <svg class="vt-empty-icon" width="44" height="44" viewBox="0 0 44 44" fill="none">
              <circle cx="22" cy="22" r="20" stroke="#334155" stroke-width="2"/>
              <circle cx="22" cy="18" r="4" fill="#334155"/>
              <rect x="19" y="25" width="6" height="11" rx="2" fill="#334155"/>
            </svg>
            <div class="vt-empty-text">
              Select a function from the list to review and validate it
            </div>
          </div>

          <!-- Validation panel -->
          <div v-else class="vt-panel">

            <!-- Node header -->
            <div class="vp-node-header">
              <div class="vp-node-name">{{ selectedNode.name }}</div>
              <div class="vp-node-meta">
                <span v-if="selectedNode.label" class="meta-pill">{{ selectedNode.label }}</span>
                <span
                  v-if="selectedNode.language"
                  class="meta-pill meta-pill--lang"
                >{{ selectedNode.language }}</span>
                <span v-if="selectedNode.source_file" class="meta-source">
                  {{ SYSTEMS.find(s => s.file === selectedNode.source_file)?.label ?? selectedNode.source_file }}
                </span>
              </div>
            </div>

            <!-- VALIDATION STATUS -->
            <div class="vp-section">
              <div class="vp-section-label">Validation Status</div>
              <div class="status-btn-group">
                <button
                  class="status-btn"
                  :class="{ 'status-btn--active': form.validated_status === 'confirmed' }"
                  :style="form.validated_status === 'confirmed'
                    ? { background: '#10b981', borderColor: '#10b981', color: '#fff' } : {}"
                  @click="form.validated_status = 'confirmed'"
                >Confirm Correct</button>
                <button
                  class="status-btn"
                  :class="{ 'status-btn--active': form.validated_status === 'incorrect' }"
                  :style="form.validated_status === 'incorrect'
                    ? { background: '#ef4444', borderColor: '#ef4444', color: '#fff' } : {}"
                  @click="form.validated_status = 'incorrect'"
                >Mark Incorrect</button>
                <button
                  class="status-btn"
                  :class="{ 'status-btn--active': form.validated_status === 'needs_clarification' }"
                  :style="form.validated_status === 'needs_clarification'
                    ? { background: '#f59e0b', borderColor: '#f59e0b', color: '#000' } : {}"
                  @click="form.validated_status = 'needs_clarification'"
                >Needs Clarification</button>
              </div>
            </div>

            <!-- CHANGE REQUIRED -->
            <div class="vp-section">
              <div class="vp-section-label">Change Required</div>
              <div class="toggle-group">
                <button
                  class="toggle-btn"
                  :class="{ 'toggle-btn--active': form.change_required }"
                  @click="form.change_required = true"
                >Yes</button>
                <button
                  class="toggle-btn"
                  :class="{ 'toggle-btn--active': !form.change_required }"
                  @click="form.change_required = false"
                >No</button>
              </div>
            </div>

            <!-- PEPPOL FIELDS -->
            <div class="vp-section">
              <div class="vp-section-label">Peppol Fields</div>
              <div class="peppol-pills">
                <span
                  v-for="field in form.peppol_fields"
                  :key="field"
                  class="peppol-pill"
                >
                  {{ field }}
                  <button class="pill-remove" @click="removePeppolField(field)">&#x2715;</button>
                </span>
                <span v-if="form.peppol_fields.length === 0" class="peppol-empty">None</span>
              </div>
              <div class="inline-add-row">
                <input
                  v-model="newFieldInput"
                  class="vp-input"
                  placeholder="e.g. BT-031"
                  @keydown.enter="addPeppolField"
                />
                <button class="vp-add-btn" @click="addPeppolField">Add</button>
              </div>
            </div>

            <!-- CALLS -->
            <div class="vp-section">
              <div class="vp-section-label">Calls (outgoing)</div>
              <div class="calls-list">
                <div
                  v-for="edge in outgoingEdges"
                  :key="edge.id"
                  class="call-row"
                >
                  <span class="call-arrow">&#8594;</span>
                  <span class="call-target">
                    {{ allNodes.find(n => n.id === edge.to_id)?.name ?? edge.to_id }}
                  </span>
                  <button class="call-remove-btn" @click="doRemoveCall(edge)">Remove</button>
                </div>
                <div v-if="outgoingEdges.length === 0" class="calls-empty">No outgoing calls</div>
              </div>
              <div class="calls-add-wrap">
                <div class="inline-add-row">
                  <div class="calls-input-wrap">
                    <input
                      v-model="addCallInput"
                      class="vp-input"
                      placeholder="Search node name..."
                      @input="onAddCallInput"
                      @focus="onAddCallInput"
                      @blur="hideDropdown"
                      @keydown.enter="onAddCallClick"
                    />
                    <div
                      v-if="showDropdown && addCallSuggestions.length > 0"
                      class="calls-dropdown"
                    >
                      <button
                        v-for="node in addCallSuggestions"
                        :key="node.id"
                        class="dropdown-item"
                        @mousedown.prevent="selectAddCallTarget(node)"
                      >{{ node.name }}</button>
                    </div>
                  </div>
                  <button
                    class="vp-add-btn"
                    :disabled="addCallLoading"
                    @click="onAddCallClick"
                  >{{ addCallLoading ? '...' : 'Add Call' }}</button>
                </div>
                <div v-if="addCallError" class="inline-error">{{ addCallError }}</div>
              </div>
            </div>

            <!-- REVIEWER NOTES -->
            <div class="vp-section">
              <div class="vp-section-label">Reviewer Notes</div>
              <textarea
                v-model="form.validation_notes"
                class="vp-textarea"
                placeholder="Add notes about this node..."
                rows="3"
              ></textarea>
            </div>

            <!-- SAVE -->
            <div class="vp-section vp-save-section">
              <button class="save-btn" :disabled="saving" @click="save">
                {{ saving ? 'Saving...' : 'Save to Knowledge Graph' }}
              </button>
              <span v-if="saveSuccess" class="save-success">Saved</span>
              <span v-if="saveError" class="save-error">{{ saveError }}</span>
            </div>

          </div>
        </div>

      </div>
    </template>

  </div>
</template>

<style scoped>
/* ── Root ────────────────────────────────────────────────────────────────── */
.validate-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f172a;
  overflow: hidden;
}

/* ── Header ──────────────────────────────────────────────────────────────── */
.vt-header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 10px 20px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.vt-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.vt-title {
  font-size: 14px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.01em;
}

.vt-sep { color: #475569; }

.vt-subtitle {
  font-size: 13px;
  color: #64748b;
}

.vt-header-center {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 200px;
}

.progress-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-track {
  flex: 1;
  height: 6px;
  background: #334155;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #10b981;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-label {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.pstat { font-weight: 600; }
.pstat--confirmed { color: #10b981; }
.pstat--incorrect { color: #ef4444; }
.pstat--unclear   { color: #f59e0b; }
.pstat-sep        { color: #475569; }

/* ── Loading / error ─────────────────────────────────────────────────────── */
.vt-state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  font-size: 13px;
  color: #64748b;
}
.vt-state--error { color: #f87171; }

/* ── System grid ─────────────────────────────────────────────────────────── */
.system-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
  padding: 12px 16px;
  background: #0a1020;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
}

.system-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 0.15s, background 0.15s;
}

.system-card:hover {
  border-color: #475569;
  background: #263348;
}

.system-card--active {
  border-color: #3b82f6;
  background: #1e3a5f;
}

.sc-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
}

.sc-label {
  font-size: 12px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1.25;
}

.sc-lang-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}

.sc-lang--abap {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.sc-lang--java {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.sc-file {
  font-size: 9px;
  font-family: monospace;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sc-progress-track {
  height: 3px;
  background: #334155;
  border-radius: 2px;
  overflow: hidden;
}

.sc-progress-fill {
  height: 100%;
  background: #10b981;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.sc-counts {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.sc-count {
  font-size: 10px;
  color: #64748b;
}

.sc-count--changed   { color: #f59e0b; }
.sc-count--confirmed { color: #10b981; }
.sc-count-sep        { font-size: 10px; color: #334155; }

/* ── Body ────────────────────────────────────────────────────────────────── */
.vt-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Left: function list ─────────────────────────────────────────────────── */
.vt-left {
  flex: 1;
  min-width: 0;
  border-right: 1px solid #334155;
  overflow-y: auto;
  background: #0f172a;
}

.vt-left::-webkit-scrollbar { width: 4px; }
.vt-left::-webkit-scrollbar-track { background: #0f172a; }
.vt-left::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

.fn-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 13px;
  color: #475569;
  padding: 40px;
  text-align: center;
}

.fn-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
}

.fn-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-left-width: 3px;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  min-width: 0;
  transition: background 0.12s, border-left-color 0.12s;
}

.fn-row:hover {
  background: #1e293b;
  border-left-color: #334155;
}

.fn-row--selected {
  background: #1e3a5f;
  border-left-color: #3b82f6;
}

.fn-row--selected:hover {
  background: #1e3a5f;
  border-left-color: #3b82f6;
}

.fn-name {
  flex: 1;
  font-size: 12px;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
  min-width: 0;
}

.fn-type-pill {
  font-size: 9px;
  font-weight: 600;
  padding: 1px 5px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 3px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  white-space: nowrap;
}

.fn-row--selected .fn-type-pill {
  background: #0f172a;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.change-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  background: #f59e0b;
  color: #000;
  font-size: 9px;
  font-weight: 800;
  border-radius: 50%;
  flex-shrink: 0;
  line-height: 1;
}

/* ── Right: validation panel ─────────────────────────────────────────────── */
.vt-right {
  width: 400px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #0f172a;
}

.vt-right::-webkit-scrollbar { width: 5px; }
.vt-right::-webkit-scrollbar-track { background: #0f172a; }
.vt-right::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

/* ── Empty state ─────────────────────────────────────────────────────────── */
.vt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  padding: 40px;
}

.vt-empty-icon { opacity: 0.35; }

.vt-empty-text {
  font-size: 13px;
  color: #475569;
  text-align: center;
  max-width: 240px;
  line-height: 1.6;
}

/* ── Validation panel ────────────────────────────────────────────────────── */
.vt-panel {
  display: flex;
  flex-direction: column;
}

/* Node header */
.vp-node-header {
  padding: 16px 20px 14px;
  border-bottom: 1px solid #334155;
  background: #1e293b;
}

.vp-node-name {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
  word-break: break-all;
  line-height: 1.3;
  margin-bottom: 8px;
}

.vp-node-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.meta-pill {
  display: inline-block;
  padding: 2px 8px;
  border: 1px solid #334155;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: #0f172a;
}

.meta-pill--lang {
  border-color: rgba(16, 185, 129, 0.35);
  color: #34d399;
  background: rgba(16, 185, 129, 0.08);
}

.meta-source {
  font-size: 10px;
  color: #475569;
  font-family: monospace;
  word-break: break-all;
}

/* Sections */
.vp-section {
  padding: 14px 20px;
  border-bottom: 1px solid #1e293b;
}

.vp-section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #475569;
  margin-bottom: 10px;
}

/* Status buttons */
.status-btn-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-btn {
  width: 100%;
  padding: 8px 14px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.status-btn:hover:not(.status-btn--active) {
  background: #263348;
  border-color: #475569;
  color: #f1f5f9;
}

/* Toggle */
.toggle-group {
  display: flex;
  gap: 6px;
}

.toggle-btn {
  flex: 1;
  padding: 7px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.toggle-btn--active {
  background: #1d4ed8;
  border-color: #3b82f6;
  color: #fff;
}

.toggle-btn:hover:not(.toggle-btn--active) {
  background: #263348;
  border-color: #475569;
  color: #f1f5f9;
}

/* Peppol pills */
.peppol-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  min-height: 22px;
  align-items: center;
}

.peppol-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  font-family: monospace;
  color: #a78bfa;
}

.peppol-empty {
  font-size: 11px;
  color: #475569;
  font-style: italic;
}

.pill-remove {
  background: none;
  border: none;
  color: #7c3aed;
  cursor: pointer;
  font-size: 10px;
  padding: 0 1px;
  line-height: 1;
  display: flex;
  align-items: center;
}
.pill-remove:hover { color: #ef4444; }

/* Inline add row (peppol + calls) */
.inline-add-row {
  display: flex;
  gap: 6px;
}

/* Inputs */
.vp-input {
  flex: 1;
  padding: 6px 10px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #f1f5f9;
  font-size: 12px;
  outline: none;
  min-width: 0;
  width: 100%;
}
.vp-input:focus { border-color: #475569; }
.vp-input::placeholder { color: #475569; }

.vp-add-btn {
  padding: 6px 12px;
  background: #1e293b;
  border: 1px solid #475569;
  border-radius: 5px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}
.vp-add-btn:hover:not(:disabled) { background: #263348; color: #f1f5f9; }
.vp-add-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* CALLS list */
.calls-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.call-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 4px;
}

.call-arrow {
  font-size: 11px;
  color: #475569;
  flex-shrink: 0;
}

.call-target {
  flex: 1;
  font-size: 12px;
  color: #94a3b8;
  font-family: monospace;
  word-break: break-all;
}

.call-remove-btn {
  padding: 2px 8px;
  background: none;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #64748b;
  font-size: 10px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s;
}
.call-remove-btn:hover { border-color: #ef4444; color: #ef4444; }

.calls-empty {
  font-size: 11px;
  color: #475569;
  font-style: italic;
}

.calls-add-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.calls-input-wrap {
  flex: 1;
  position: relative;
  min-width: 0;
}

.calls-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 200;
  background: #1e293b;
  border: 1px solid #475569;
  border-top: none;
  border-radius: 0 0 5px 5px;
  max-height: 180px;
  overflow-y: auto;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 7px 10px;
  background: none;
  border: none;
  border-bottom: 1px solid #334155;
  color: #94a3b8;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  font-family: monospace;
}
.dropdown-item:last-child { border-bottom: none; }
.dropdown-item:hover { background: #263348; color: #f1f5f9; }

.inline-error {
  font-size: 11px;
  color: #f87171;
}

/* Textarea */
.vp-textarea {
  width: 100%;
  padding: 8px 10px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #f1f5f9;
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  font-family: inherit;
}
.vp-textarea:focus { border-color: #475569; }
.vp-textarea::placeholder { color: #475569; }

/* Save section */
.vp-save-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  border-bottom: none;
  padding-bottom: 20px;
}

.save-btn {
  padding: 9px 20px;
  background: #1d4ed8;
  border: 1px solid #3b82f6;
  border-radius: 5px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.save-btn:hover:not(:disabled) { background: #2563eb; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.save-success {
  font-size: 12px;
  color: #10b981;
  font-weight: 600;
}

.save-error {
  font-size: 12px;
  color: #f87171;
}

/* ── Header right: confidence score ──────────────────────────────────────── */
.vt-header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
  margin-left: auto;
}

.confidence-score {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  transition: color 0.3s ease;
}

.confidence-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
}

.confidence-detail {
  font-size: 10px;
  color: #475569;
  white-space: nowrap;
}

/* ── Validation queue strip ───────────────────────────────────────────────── */
.queue-strip {
  background: #1e293b;
  border-bottom: 1px solid #334155;
  padding: 8px 16px;
  flex-shrink: 0;
}

.queue-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.queue-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.queue-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #94a3b8;
}

.queue-badge {
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  background: #ef4444;
  border-radius: 999px;
  padding: 1px 8px;
  white-space: nowrap;
}

.queue-toggle-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: none;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.queue-toggle-btn:hover {
  border-color: #475569;
  color: #94a3b8;
}

.queue-toggle-arrow {
  font-size: 8px;
}

.queue-cards-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.queue-cards-row::-webkit-scrollbar {
  height: 3px;
}
.queue-cards-row::-webkit-scrollbar-track {
  background: #1e293b;
}
.queue-cards-row::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 2px;
}

.queue-all-clear {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  padding: 8px 0;
}

.queue-card {
  flex-shrink: 0;
  width: 160px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.queue-card:hover {
  border-color: #475569;
  background: #111d30;
}

.qc-status-badge {
  display: inline-block;
  align-self: flex-start;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  color: #fff;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.qc-system {
  font-size: 11px;
  font-weight: 700;
  color: #f1f5f9;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}

.qc-name {
  font-size: 10px;
  font-family: monospace;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-change {
  font-size: 10px;
  font-weight: 600;
}

.qc-change--required {
  color: #ef4444;
}

.qc-change--none {
  color: #475569;
}
</style>
