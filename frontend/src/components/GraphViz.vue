<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({ nodes: [], edges: [] })
  }
})

// ── vis-network handles ──────────────────────────────────────────────────────
const container = ref(null)
let network = null
let nodesDs = null
let edgesDs = null

// plain Map — not reactive (no proxy overhead)
const nodeDataMap = new Map()

// ── UI state ─────────────────────────────────────────────────────────────────
const layoutMode   = ref('network')   // 'network' | 'flow'
const visibleTypes = ref(new Set())   // edge type strings currently shown
const selectedNode = ref(null)        // node object from graphData.nodes

// ── Color / shape maps ───────────────────────────────────────────────────────
const KG_COLORS = {
  systems: '#3b82f6',
  process: '#10b981',
  data:    '#f59e0b',
  entity:  '#8b5cf6'
}

const LABEL_SHAPES = {
  Application:      'dot',
  ProcessStep:      'box',
  BusinessFunction: 'box',
  Table:            'database',
  Column:           'ellipse',
  Obligation:       'diamond',
  Regulation:       'diamond'
}

const EDGE_TYPE_COLORS = {
  CALLS:      '#3b82f6',
  READS_FROM: '#f59e0b',
  DEPENDS_ON: '#8b5cf6',
  STORES_IN:  '#10b981',
  GOVERNS:    '#ef4444',
  MAPS_TO:    '#06b6d4',
  CONTAINS:   '#64748b'
}
const DEFAULT_EDGE_COLOR = '#475569'

// ── Derived edge types from current prop ─────────────────────────────────────
const edgeTypes = computed(() => {
  const edges = props.graphData?.edges ?? []
  const types = new Set()
  edges.forEach(e => { if (e.label) types.add(e.label) })
  return [...types].sort()
})

// ── vis-node / vis-edge converters ───────────────────────────────────────────
function toVisNode(n) {
  const color = KG_COLORS[n.kg] || '#64748b'
  const shape = LABEL_SHAPES[n.label] || 'ellipse'
  return {
    id: n.id,
    label: n.name || n.id,
    shape,
    color: {
      background: color,
      border: color,
      highlight: { background: '#ffffff', border: color },
      hover: { background: color + 'cc', border: color }
    },
    font: { color: '#f1f5f9', size: 12 },
    borderWidth: 1,
    title: `${n.label} [${n.kg}]\n${JSON.stringify(n.props || {}, null, 2)}`
  }
}

function toVisEdge(e) {
  const typeColor = EDGE_TYPE_COLORS[e.label] || DEFAULT_EDGE_COLOR
  return {
    id: e.id,
    from: e.from_id,
    to: e.to_id,
    label: e.label,
    hidden: false,
    font: {
      color: '#f1f5f9',
      size: 11,
      align: 'middle',
      background: 'rgba(15, 23, 42, 0.88)',
      strokeWidth: 0
    },
    color: {
      color:     typeColor,
      highlight: typeColor + 'cc',
      hover:     typeColor + 'aa'
    },
    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
    smooth: { type: 'curvedCW', roundness: 0.15 }
  }
}

// ── Base network options ──────────────────────────────────────────────────────
const NETWORK_OPTIONS = {
  physics: {
    enabled: true,
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {
      gravitationalConstant: -50,
      centralGravity: 0.01,
      springLength: 120,
      springConstant: 0.08,
      damping: 0.4
    },
    stabilization: { iterations: 150, updateInterval: 25 }
  },
  layout: {
    improvedLayout: false,
    hierarchical: { enabled: false }
  },
  interaction: {
    hover: true,
    tooltipDelay: 200,
    navigationButtons: false,
    keyboard: false
  },
  nodes: { size: 18 },
  edges: { width: 1.5, selectionWidth: 3 }
}

const FLOW_OPTIONS = {
  physics: { enabled: false },
  layout: {
    hierarchical: {
      enabled:            true,
      direction:          'LR',
      sortMethod:         'directed',
      levelSeparation:    220,
      nodeSpacing:        100,
      parentCentralization: true,
      edgeMinimization:   true,
      blockShifting:      true
    }
  },
  interaction: {
    hover: true,
    tooltipDelay: 200,
    navigationButtons: false,
    keyboard: false
  },
  nodes: { size: 18 },
  edges: { width: 1.5, selectionWidth: 3 }
}

// ── Init network ─────────────────────────────────────────────────────────────
function initNetwork() {
  if (!container.value) return

  nodesDs = new DataSet([])
  edgesDs = new DataSet([])

  network = new Network(
    container.value,
    { nodes: nodesDs, edges: edgesDs },
    NETWORK_OPTIONS
  )

  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      selectedNode.value = nodeDataMap.get(params.nodes[0]) ?? null
    } else {
      selectedNode.value = null
    }
  })
}

// ── Apply graph data ──────────────────────────────────────────────────────────
function applyGraphData(data) {
  if (!nodesDs || !edgesDs || !network) return

  // rebuild nodeDataMap
  nodeDataMap.clear()
  ;(data.nodes || []).forEach(n => nodeDataMap.set(n.id, n))

  // reset visible types to ALL present types
  const types = new Set((data.edges || []).map(e => e.label).filter(Boolean))
  visibleTypes.value = types

  const visNodes = (data.nodes || []).map(toVisNode)
  const visEdges = (data.edges || []).map(toVisEdge)

  nodesDs.clear()
  edgesDs.clear()
  nodesDs.add(visNodes)
  edgesDs.add(visEdges)

  selectedNode.value = null

  if (visNodes.length > 0) {
    network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } })
  }
}

// ── Layout toggle ─────────────────────────────────────────────────────────────
function setLayout(mode) {
  if (!network) return
  layoutMode.value = mode
  const opts = mode === 'flow' ? FLOW_OPTIONS : NETWORK_OPTIONS
  network.setOptions(opts)
  network.fit({ animation: { duration: 600 } })
}

// ── Edge type filter pills ────────────────────────────────────────────────────
function toggleType(type) {
  if (!edgesDs) return
  const next = new Set(visibleTypes.value)
  if (next.has(type)) {
    next.delete(type)
  } else {
    next.add(type)
  }
  visibleTypes.value = next

  // update hidden flag on matching edges
  const updates = edgesDs.get().map(e => ({
    id: e.id,
    hidden: !next.has(e.label)
  }))
  edgesDs.update(updates)
}

// ── highlight() — keep existing behaviour ────────────────────────────────────
function highlight(nodeIds) {
  if (!network || !nodesDs) return
  const ids = new Set(nodeIds)
  const updates = nodesDs.get().map(n => ({
    id: n.id,
    opacity: ids.has(n.id) ? 1 : 0.2
  }))
  nodesDs.update(updates)

  if (nodeIds.length > 0) {
    network.fit({
      nodes: nodeIds,
      animation: { duration: 500, easingFunction: 'easeInOutQuad' }
    })
  }
}

defineExpose({ highlight })

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  initNetwork()
  if (props.graphData?.nodes?.length) {
    applyGraphData(props.graphData)
  }
})

watch(
  () => props.graphData,
  (val) => { if (val) applyGraphData(val) },
  { deep: true }
)

onBeforeUnmount(() => {
  if (network) {
    network.destroy()
    network = null
  }
})

// ── Node detail card helpers ──────────────────────────────────────────────────
function nodeKgColor(node) {
  return KG_COLORS[node.kg] || '#64748b'
}

function nodeProps(node) {
  if (!node.props) return []
  return Object.entries(node.props).filter(([, v]) => v !== null && v !== '' && v !== undefined)
}
</script>

<template>
  <div class="graph-wrapper">

    <!-- ── Toolbar ─────────────────────────────────────────────────────────── -->
    <div v-if="graphData && graphData.nodes && graphData.nodes.length > 0" class="toolbar">

      <!-- Layout toggle -->
      <div class="layout-group">
        <button
          class="layout-btn"
          :class="{ active: layoutMode === 'network' }"
          @click="setLayout('network')"
        >Network</button>
        <button
          class="layout-btn"
          :class="{ active: layoutMode === 'flow' }"
          @click="setLayout('flow')"
        >Flow</button>
      </div>

      <!-- Spacer -->
      <div class="toolbar-spacer"></div>

      <!-- Edge type pills -->
      <div class="pill-group">
        <button
          v-for="type in edgeTypes"
          :key="type"
          class="edge-pill"
          :class="{ active: visibleTypes.has(type) }"
          @click="toggleType(type)"
          :style="{
            '--pill-color': EDGE_TYPE_COLORS[type] || DEFAULT_EDGE_COLOR
          }"
        >
          <span class="pill-dot"></span>
          {{ type }}
        </button>
      </div>
    </div>

    <!-- ── Empty state ─────────────────────────────────────────────────────── -->
    <div v-if="!graphData || !graphData.nodes || graphData.nodes.length === 0" class="empty-state">
      <span>Select a Knowledge Graph from the sidebar to visualize</span>
    </div>

    <!-- ── Graph canvas ────────────────────────────────────────────────────── -->
    <div
      ref="container"
      class="graph-container"
      :class="{ 'with-toolbar': graphData && graphData.nodes && graphData.nodes.length > 0 }"
    ></div>

    <!-- ── Node detail card ────────────────────────────────────────────────── -->
    <transition name="card-fade">
      <div v-if="selectedNode" class="node-card">
        <button class="card-close" @click="selectedNode = null">&#x2715;</button>
        <div class="card-name">{{ selectedNode.name || selectedNode.id }}</div>
        <div class="card-badge" :style="{ background: nodeKgColor(selectedNode) + '33', color: nodeKgColor(selectedNode), borderColor: nodeKgColor(selectedNode) + '66' }">
          {{ selectedNode.label }}
        </div>
        <div class="card-kg">KG: {{ selectedNode.kg }}</div>
        <div v-if="nodeProps(selectedNode).length > 0" class="card-props">
          <div v-for="[key, val] in nodeProps(selectedNode)" :key="key" class="card-prop-row">
            <span class="prop-key">{{ key }}</span>
            <span class="prop-val">{{ val }}</span>
          </div>
        </div>
      </div>
    </transition>

    <!-- ── Legend ──────────────────────────────────────────────────────────── -->
    <div v-if="!selectedNode" class="legend">
      <div
        class="legend-item"
        v-for="(color, kg) in { systems: '#3b82f6', process: '#10b981', data: '#f59e0b', entity: '#8b5cf6' }"
        :key="kg"
      >
        <span class="legend-dot" :style="{ background: color }"></span>
        <span class="legend-label">{{ kg }}</span>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ── Wrapper ────────────────────────────────────────────────────────────────── */
.graph-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background: #0f172a;
  border-radius: 6px;
  overflow: hidden;
}

/* ── Toolbar ────────────────────────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 8px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
}
.toolbar::-webkit-scrollbar {
  display: none;
}

.toolbar-spacer {
  flex: 1;
  min-width: 8px;
}

/* Layout buttons */
.layout-group {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.layout-btn {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  border: 1px solid #334155;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  white-space: nowrap;
}
.layout-btn:hover {
  background: #1e293b;
  color: #cbd5e1;
}
.layout-btn.active {
  background: #1e40af;
  border-color: #3b82f6;
  color: #f1f5f9;
}

/* Edge type pills */
.pill-group {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.edge-pill {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border-radius: 11px;
  border: 1px solid #334155;
  background: transparent;
  color: #475569;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  white-space: nowrap;
}
.edge-pill:hover {
  border-color: var(--pill-color);
  color: var(--pill-color);
}
.edge-pill.active {
  background: color-mix(in srgb, var(--pill-color) 18%, transparent);
  border-color: var(--pill-color);
  color: var(--pill-color);
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pill-color);
  flex-shrink: 0;
  opacity: 0.5;
  transition: opacity 0.15s;
}
.edge-pill.active .pill-dot {
  opacity: 1;
}

/* ── Graph canvas ───────────────────────────────────────────────────────────── */
.graph-container {
  width: 100%;
  height: 100%;
}
.graph-container.with-toolbar {
  height: calc(100% - 36px);
}

/* ── Empty state ────────────────────────────────────────────────────────────── */
.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #334155;
  font-size: 14px;
  pointer-events: none;
  z-index: 1;
}

/* ── Node detail card ───────────────────────────────────────────────────────── */
.node-card {
  position: absolute;
  top: 48px; /* 36px toolbar + 12px gap */
  right: 12px;
  width: 240px;
  max-width: 240px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px;
  z-index: 10;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}

.card-close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 13px;
  line-height: 20px;
  text-align: center;
  border-radius: 3px;
  padding: 0;
  transition: color 0.15s;
}
.card-close:hover {
  color: #f1f5f9;
}

.card-name {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
  padding-right: 20px;
  word-break: break-word;
  margin-bottom: 6px;
}

.card-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
  border: 1px solid;
  margin-bottom: 4px;
  letter-spacing: 0.03em;
}

.card-kg {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 8px;
}

.card-props {
  border-top: 1px solid #334155;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-prop-row {
  display: flex;
  gap: 6px;
  font-size: 11px;
}

.prop-key {
  color: #64748b;
  flex-shrink: 0;
  min-width: 60px;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prop-val {
  color: #cbd5e1;
  word-break: break-word;
}

/* Card enter/leave transition */
.card-fade-enter-active,
.card-fade-leave-active {
  transition: opacity 0.18s, transform 0.18s;
}
.card-fade-enter-from,
.card-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Legend ─────────────────────────────────────────────────────────────────── */
.legend {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(30, 41, 59, 0.85);
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 8px 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: capitalize;
}
</style>
