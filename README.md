# Agentic Knowledge Graph (AKG) Platform
### Regulatory Change Impact Analysis — RCRB Demo

A full-stack AI demo that uses a **Knowledge Graph + multi-agent LLM pipeline** to assess the impact of regulatory changes on enterprise systems and processes. Built for the Belgium Mandatory B2B E-Invoicing (Peppol BIS 3.0) use case.

---

## What It Does

1. **Ingests** your SAP ABAP code, Java services, CMDB data, and regulatory documents into four connected Knowledge Graphs (Entity, Process, Systems, Data)
2. **Runs a 5-agent assessment** that streams live results via Server-Sent Events:
   - Regulation Analyst → Process Impact → Systems Impact → Data Gap → Synthesis
3. **Visualises** the cross-KG impact path from regulatory obligation → process step → application → data field
4. **HITL Validation** — a priority queue lets business users confirm or correct AI findings
5. **Semantic Layer** — editable business concept definitions (impact levels, readiness thresholds, blocker rules) that agents use instead of raw Cypher
6. **Demo Reset** — one-click reset clears validation state in Neo4j for a clean re-run

---

## Architecture

```
frontend/          Vue 3 + Vite (port 3000)
backend/           FastAPI + SSE (port 8001)
  ├── main.py         REST + SSE endpoints
  ├── agents.py       5-agent assessment pipeline (Anthropic SDK)
  ├── semantic_layer.py  Named query functions + editable CONFIG
  └── neo4j_client.py    Neo4j driver wrapper
ingestion/         Python scripts to seed the Knowledge Graphs
data/              Source artefacts (ABAP, Java, CMDB JSON, regulations)
```

**Knowledge Graphs (all in one Neo4j Community Edition database):**

| KG | Node Types | Description |
|---|---|---|
| Entity | `Regulation`, `Obligation` | Belgium e-invoicing rules + Peppol BT fields |
| Process | `ProcessStep`, `BusinessFunction`, `Decision`, `Exception` | O2C ABAP/Java implementation steps |
| Systems | `Application` | SAP S/4HANA, Peppol SMP, ServiceNow CMDB |
| Data | `Table`, `Column` | SAP data dictionary fields |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Neo4j Community | 2026.x or 5.x | `brew install neo4j` |
| Python | 3.11+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | `brew install node` |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com) |

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/AltimetrikAI/akg-rcrb-demo.git
cd akg-rcrb-demo
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and Neo4j password
```

### 2. Start Neo4j

```bash
brew services start neo4j
# Wait ~15s then verify: nc -z localhost 7687 && echo "ready"
```

Set your Neo4j password via the browser at `http://localhost:7474` or:
```bash
cypher-shell -u neo4j -p neo4j "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'your-password'"
```
Then update `NEO4J_PASSWORD` in your `.env`.

### 3. Seed the Knowledge Graphs

```bash
cd ingestion
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
python build_graphs.py
```

This creates all four KGs with ~164 nodes and ~412 edges.

### 4. Start the backend

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
# or: .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001
```

Verify: `curl http://localhost:8001/` → `{"status":"ok"}`

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Demo Flow

1. **Scenario tab** — overview of the Belgium e-invoicing regulation + compliance status (appears after running assessment)
2. **Knowledge Graphs tab** — explore all four KGs visually; click nodes to inspect properties
3. **Run RCRB Assessment** (top-right button) — 5 agents stream their analysis live
4. **Process Flow tab** — Order-to-Cash pipeline with change impact highlighted per stage
5. **Source Data tab** — browse the ABAP/Java/CMDB/regulation source files
6. **Semantic Layer tab** — edit business concept definitions live (e.g. change what counts as a "critical blocker")
7. **Validate tab** — HITL queue; confirm/reject AI findings; watch the KG Confidence Score rise
8. **Reset Demo** (top-right button) — clears validation state for a clean re-run

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/assess` | SSE stream — runs 5-agent assessment |
| `GET` | `/api/graph/kg/{kg}` | Graph data for one KG |
| `GET` | `/api/semantic/status` | Compliance readiness score + blockers |
| `PATCH` | `/api/semantic/config` | Update semantic layer definitions live |
| `PATCH` | `/api/validate/node/{id}` | HITL: confirm/reject a process node |
| `POST` | `/api/demo/reset` | Clear all validation state for re-demo |

Full docs: `http://localhost:8001/docs`

---

## Project Structure

```
.
├── backend/
│   ├── agents.py           # 5-agent pipeline using Anthropic SDK
│   ├── main.py             # FastAPI app + all endpoints
│   ├── neo4j_client.py     # Neo4j query/write helpers
│   ├── semantic_layer.py   # Named queries + editable CONFIG dict
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue                    # Root layout, tabs, assessment trigger
│   │   ├── api.js                     # All fetch/SSE calls
│   │   └── components/
│   │       ├── ScenarioTab.vue        # Compliance overview
│   │       ├── GraphViz.vue           # vis-network KG visualisation
│   │       ├── AssessmentPanel.vue    # Live streaming agent results
│   │       ├── ProcessFlowView.vue    # O2C pipeline + change impact
│   │       ├── SourceExplorer.vue     # Source file viewer
│   │       ├── SemanticLayerTab.vue   # Live-edit concept definitions
│   │       └── ValidateTab.vue        # HITL queue + confidence score
│   ├── package.json
│   └── vite.config.js
├── ingestion/
│   ├── build_graphs.py     # Entry point — seeds all 4 KGs
│   ├── entity_kg.py        # Regulations + Obligations
│   ├── process_kg.py       # O2C process steps
│   ├── systems_kg.py       # Applications (CMDB)
│   ├── data_kg.py          # SAP tables + columns
│   └── bridge_builder.py   # Cross-KG relationships
├── data/                   # Source artefacts used by ingestion
├── .env.example            # Copy to .env and fill in credentials
└── docker-compose.yml      # Optional: run Neo4j via Docker
```

---

## Docker (optional Neo4j)

If you prefer Docker over Homebrew for Neo4j:

```bash
docker-compose up -d neo4j
# Wait for bolt://localhost:7687 to be ready, then run ingestion
```

---

## Adapting This Demo

The semantic layer (`backend/semantic_layer.py`) is the key customisation point:

- `CONFIG` dict — change what counts as a critical blocker, readiness thresholds, impact levels
- Named query functions (`get_compliance_summary`, `get_critical_blockers`, etc.) — swap in your own Cypher for a different domain
- Agent prompts in `backend/agents.py` — update for your regulation/use case

The ingestion scripts in `ingestion/` define the full data model — replace with your own source data to build a different KG.
