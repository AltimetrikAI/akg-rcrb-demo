<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchSources, fetchSourceFile } from '../api.js'

const SOURCE_GROUPS = [
  { key: 'abap',        label: 'SAP ABAP' },
  { key: 'java',        label: 'Java Microservices' },
  { key: 'cmdb',        label: 'ServiceNow CMDB' },
  { key: 'sap_dd',      label: 'SAP Data Dictionary' },
  { key: 'regulations', label: 'Regulation' },
  { key: 'sharepoint',  label: 'SharePoint / Prior RCRBs' },
]

const LANGUAGE_LABELS = {
  abap:     'ABAP',
  java:     'Java',
  json:     'JSON',
  markdown: 'Markdown',
  text:     'Text',
}

// ── State ──────────────────────────────────────────────────────────────────
const sources       = ref({})
const sourcesLoading = ref(false)
const sourcesError  = ref(null)

const selectedFile  = ref(null)
const fileContent   = ref(null)
const fileLanguage  = ref(null)
const fileLoading   = ref(false)
const fileError     = ref(null)
const copySuccess   = ref(false)

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(async () => {
  sourcesLoading.value = true
  try {
    sources.value = await fetchSources()
  } catch (e) {
    sourcesError.value = 'Failed to load source list'
    console.error(e)
  } finally {
    sourcesLoading.value = false
  }
})

// ── File selection ─────────────────────────────────────────────────────────
async function selectFile(filename) {
  if (selectedFile.value === filename) return
  selectedFile.value = filename
  fileContent.value  = null
  fileLanguage.value = null
  fileError.value    = null
  fileLoading.value  = true
  try {
    const data = await fetchSourceFile(filename)
    fileContent.value  = data.content
    fileLanguage.value = data.language
  } catch (e) {
    fileError.value = 'Failed to load file content'
    console.error(e)
  } finally {
    fileLoading.value = false
  }
}

// ── Derived data ───────────────────────────────────────────────────────────
const numberedLines = computed(() => {
  if (!fileContent.value) return []
  return fileContent.value.split('\n').map((line, index) => ({ line, index }))
})

const languageLabel = computed(() =>
  LANGUAGE_LABELS[fileLanguage.value] ?? fileLanguage.value ?? ''
)

// ── Helpers ────────────────────────────────────────────────────────────────
function getLineClass(line) {
  if (line.includes('CHANGE REQUIRED')) return 'line--amber'
  if (/BT-031|BT-048|BT-9|BG-23|BT-5/.test(line)) return 'line--green'
  return ''
}

function fileCount(key) {
  const list = sources.value[key]
  return Array.isArray(list) ? list.length : 0
}

async function copyContent() {
  if (!fileContent.value) return
  try {
    await navigator.clipboard.writeText(fileContent.value)
    copySuccess.value = true
    setTimeout(() => { copySuccess.value = false }, 2000)
  } catch (e) {
    console.error('Copy failed', e)
  }
}
</script>

<template>
  <div class="source-explorer">

    <!-- ── File tree (left column) ──────────────────────────────────────── -->
    <div class="file-tree">
      <div v-if="sourcesLoading" class="tree-state">Loading...</div>
      <div v-else-if="sourcesError" class="tree-state tree-state--error">{{ sourcesError }}</div>
      <template v-else>
        <div
          v-for="group in SOURCE_GROUPS"
          :key="group.key"
          class="tree-group"
        >
          <div class="tree-group-header">
            <span class="tree-group-label">{{ group.label }}</span>
            <span class="tree-group-count">{{ fileCount(group.key) }}</span>
          </div>
          <button
            v-for="filename in (sources[group.key] || [])"
            :key="filename"
            class="tree-file"
            :class="{ 'tree-file--active': selectedFile === filename }"
            :title="filename"
            @click="selectFile(filename)"
          >
            {{ filename }}
          </button>
        </div>
      </template>
    </div>

    <!-- ── Code viewer (right column) ──────────────────────────────────── -->
    <div class="code-viewer">

      <!-- Placeholder -->
      <div v-if="!selectedFile" class="viewer-placeholder">
        Select a source file to view its content
      </div>

      <template v-else>
        <!-- Viewer header -->
        <div class="viewer-header">
          <span class="viewer-filename">{{ selectedFile }}</span>
          <span
            v-if="fileLanguage"
            class="lang-badge"
            :class="`lang-badge--${fileLanguage}`"
          >{{ languageLabel }}</span>
          <span class="viewer-spacer"></span>
          <button
            class="copy-btn"
            :class="{ 'copy-btn--ok': copySuccess }"
            :disabled="!fileContent"
            @click="copyContent"
          >
            {{ copySuccess ? 'Copied' : 'Copy' }}
          </button>
        </div>

        <!-- Loading / error -->
        <div v-if="fileLoading" class="viewer-state">Loading...</div>
        <div v-else-if="fileError" class="viewer-state viewer-state--error">{{ fileError }}</div>

        <!-- Code content -->
        <div v-else-if="fileContent !== null" class="code-scroll">
          <div class="code-lines">
            <div
              v-for="item in numberedLines"
              :key="item.index"
              class="code-line"
              :class="getLineClass(item.line)"
            ><span class="line-text">{{ item.line }}</span></div>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
.source-explorer {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── File tree ───────────────────────────────────────────────────────────── */
.file-tree {
  width: 200px;
  flex-shrink: 0;
  background: #1e293b;
  border-right: 1px solid #334155;
  overflow-y: auto;
  padding: 8px 0;
}

.file-tree::-webkit-scrollbar        { width: 5px; }
.file-tree::-webkit-scrollbar-track  { background: #0f172a; }
.file-tree::-webkit-scrollbar-thumb  { background: #334155; border-radius: 3px; }

.tree-state {
  padding: 16px;
  font-size: 12px;
  color: #64748b;
}
.tree-state--error { color: #f87171; }

.tree-group {
  margin-bottom: 4px;
}

.tree-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 4px;
  gap: 6px;
}

.tree-group-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
}

.tree-group-count {
  font-size: 9px;
  font-weight: 600;
  color: #334155;
  background: #0f172a;
  border-radius: 10px;
  padding: 1px 6px;
}

.tree-file {
  display: block;
  width: 100%;
  padding: 6px 12px;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 11px;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: background 0.1s, color 0.1s;
  line-height: 1.4;
}

.tree-file:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #f1f5f9;
}

.tree-file--active {
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
  border-left: 2px solid #3b82f6;
  padding-left: 10px;
}

/* ── Code viewer ─────────────────────────────────────────────────────────── */
.code-viewer {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #0f172a;
  overflow: hidden;
}

.viewer-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #475569;
  font-style: italic;
}

.viewer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  min-width: 0;
}

.viewer-filename {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 1;
  min-width: 0;
}

.viewer-spacer { flex: 1; }

/* Language badge */
.lang-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

.lang-badge--abap     { background: rgba(59, 130, 246, 0.2);  color: #93c5fd; }
.lang-badge--java     { background: rgba(16, 185, 129, 0.2);  color: #6ee7b7; }
.lang-badge--json     { background: rgba(245, 158, 11, 0.2);  color: #fcd34d; }
.lang-badge--markdown { background: rgba(139, 92, 246, 0.2);  color: #c4b5fd; }
.lang-badge--text     { background: rgba(100, 116, 139, 0.2); color: #94a3b8; }

/* Copy button */
.copy-btn {
  padding: 4px 12px;
  background: #1e3a5f;
  border: 1px solid #3b82f6;
  color: #93c5fd;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.copy-btn:hover:not(:disabled) {
  background: #2563eb;
  color: #fff;
}

.copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.copy-btn--ok {
  background: rgba(16, 185, 129, 0.2);
  border-color: #10b981;
  color: #6ee7b7;
}

/* Viewer state messages */
.viewer-state {
  padding: 24px;
  font-size: 12px;
  color: #64748b;
}
.viewer-state--error { color: #f87171; }

/* ── Code content ────────────────────────────────────────────────────────── */
.code-scroll {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.code-scroll::-webkit-scrollbar        { width: 6px; height: 6px; }
.code-scroll::-webkit-scrollbar-track  { background: #0f172a; }
.code-scroll::-webkit-scrollbar-thumb  { background: #334155; border-radius: 3px; }

.code-lines {
  counter-reset: line-counter;
  font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  padding-bottom: 24px;
}

.code-line {
  counter-increment: line-counter;
  display: flex;
  align-items: stretch;
  min-height: 1.7em;
}

.code-line::before {
  content: counter(line-counter);
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 52px;
  padding: 0 12px;
  color: #334155;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  user-select: none;
  flex-shrink: 0;
  font-size: 11px;
}

.line-text {
  padding: 0 16px;
  white-space: pre;
  flex: 1;
}

/* Line highlights */
.line--amber {
  background: rgba(245, 158, 11, 0.12);
}
.line--amber::before {
  background: rgba(245, 158, 11, 0.08);
}
.line--amber .line-text {
  color: #fef3c7;
}

.line--green {
  background: rgba(16, 185, 129, 0.08);
}
.line--green::before {
  background: rgba(16, 185, 129, 0.05);
}
.line--green .line-text {
  color: #d1fae5;
}
</style>
