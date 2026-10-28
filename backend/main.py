"""
HPE AKG Platform — FastAPI Backend
"""
import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import neo4j_client as db
from agents import run_assessment
import semantic_layer as sem

app = FastAPI(title="HPE AKG Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Graph Data Endpoints ──────────────────────────────────────────────────────

@app.get("/api/graph/all")
def get_full_graph():
    """Return all nodes and edges for vis-network visualization."""
    nodes = db.query(
        """
        MATCH (n)
        RETURN elementId(n) AS id,
               labels(n)[0] AS label,
               n.name AS name,
               n.kg AS kg,
               properties(n) AS props
        LIMIT 300
        """
    )
    edges = db.query(
        """
        MATCH (a)-[r]->(b)
        RETURN elementId(r) AS id,
               elementId(a) AS from_id,
               elementId(b) AS to_id,
               type(r) AS label
        LIMIT 500
        """
    )
    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/kg/{kg_name}")
def get_kg_subgraph(kg_name: str):
    """Return nodes and edges for a specific KG (systems|process|data|entity)."""
    nodes = db.query(
        "MATCH (n {kg: $kg}) RETURN elementId(n) AS id, labels(n)[0] AS label, "
        "n.name AS name, n.kg AS kg, properties(n) AS props",
        kg=kg_name,
    )
    edges = db.query(
        """
        MATCH (a {kg: $kg})-[r]->(b {kg: $kg})
        RETURN elementId(r) AS id, elementId(a) AS from_id,
               elementId(b) AS to_id, type(r) AS label
        """,
        kg=kg_name,
    )
    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/impact-path")
def get_impact_path(obligation_id: str = Query(default="OBL-BT-048")):
    """Return the full cross-KG impact path for one obligation."""
    # Obligation -> ProcessStep -> Application -> Table -> Column
    result = db.query(
        """
        MATCH (o:Obligation {id: $obl_id})
        OPTIONAL MATCH (o)-[:GOVERNS]->(s)
        OPTIONAL MATCH (s)-[:EXECUTED_BY]->(a:Application)
        OPTIONAL MATCH (o)-[:MAPS_TO]->(c:Column)
        OPTIONAL MATCH (tbl:Table)-[:CONTAINS_FIELD]->(c)
        RETURN o, collect(DISTINCT s) AS steps,
               collect(DISTINCT a) AS apps,
               collect(DISTINCT c) AS columns,
               collect(DISTINCT tbl) AS tables
        """,
        obl_id=obligation_id,
    )
    return result


@app.get("/api/obligations")
def list_obligations():
    return db.query(
        """
        MATCH (r:Regulation)-[:REQUIRES]->(o:Obligation)
        RETURN o.id AS id, o.bt_field AS field, o.name AS name,
               o.impact_level AS impact, o.change_required AS change_required,
               o.gap_description AS gap
        ORDER BY o.impact_level DESC, o.bt_field
        """
    )


# ── Semantic Layer Endpoints ──────────────────────────────────────────────────

@app.get("/api/semantic/status")
def get_semantic_status(country: str = Query(default="BE")):
    """
    Compliance readiness dashboard: readiness score, status label, counts,
    and the list of unresolved critical blockers.
    """
    summary  = sem.get_compliance_summary(country)
    blockers = sem.get_critical_blockers(country)
    return {
        "summary":  summary,
        "blockers": blockers,
    }


@app.get("/api/semantic/critical-blockers")
def get_critical_blockers(country: str = Query(default="BE")):
    """List unresolved critical obligations (impact levels defined in config)."""
    return sem.get_critical_blockers(country)


@app.get("/api/semantic/readiness")
def get_readiness_score(country: str = Query(default="BE")):
    """Compliance readiness score (0-100) with status label and breakdown."""
    return sem.get_compliance_summary(country)


@app.get("/api/semantic/config")
def get_semantic_config():
    """Return the current semantic layer configuration (concept definitions)."""
    return sem.get_config()


@app.patch("/api/semantic/config")
def update_semantic_config(updates: dict):
    """
    Update semantic layer concept definitions at runtime.
    Changes take effect immediately — no restart required.
    Supported keys: impact_levels, readiness_thresholds, change_types, critical_blocker_rule.
    """
    updated = sem.update_config(updates)
    return {"status": "updated", "config": updated}


@app.get("/api/applications")
def list_applications():
    return db.query(
        "MATCH (a:Application) RETURN a.sys_id AS sys_id, a.name AS name, "
        "a.tier AS tier, a.owner AS owner, a.hosting AS hosting ORDER BY a.tier, a.name"
    )


SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SOURCE_FILE_MAP = {
    # ABAP
    "Z_HPE_INVOICE_CREATE.abap":  ("sap/abap/Z_HPE_INVOICE_CREATE.abap",  "abap"),
    "Z_HPE_VATCHECK.abap":        ("sap/abap/Z_HPE_VATCHECK.abap",        "abap"),
    "Z_HPE_PEPPOL_OUTPUT.abap":   ("sap/abap/Z_HPE_PEPPOL_OUTPUT.abap",   "abap"),
    "Z_HPE_FI_TAXPOST.abap":      ("sap/abap/Z_HPE_FI_TAXPOST.abap",      "abap"),
    # Java
    "InvoiceDeliveryService.java": ("java/src/InvoiceDeliveryService.java", "java"),
    "PeppolRouter.java":           ("java/src/PeppolRouter.java",           "java"),
    "CustomerVatService.java":     ("java/src/CustomerVatService.java",     "java"),
    "TaxDeterminationService.java":("java/src/TaxDeterminationService.java","java"),
    "BelgianVatValidator.java":    ("java/src/BelgianVatValidator.java",    "java"),
    # CMDB
    "servicenow_cmdb_ci.json":     ("cmdb/servicenow_cmdb_ci.json",        "json"),
    "servicenow_cmdb_rel.json":    ("cmdb/servicenow_cmdb_rel.json",        "json"),
    # SAP DD
    "tables.json":                 ("sap/dd/tables.json",                  "json"),
    "fields.json":                 ("sap/dd/fields.json",                  "json"),
    # Regulation
    "belgium_einvoicing.txt":      ("regulations/belgium_einvoicing.txt",  "text"),
    # SharePoint
    "RCRB-2023-France-eInvoice.md":("sharepoint/RCRB-2023-France-eInvoice.md","markdown"),
    "HPE-eInvoice-Policy.md":      ("sharepoint/HPE-eInvoice-Policy.md",   "markdown"),
}


@app.get("/api/source/{filename}")
def get_source_file(filename: str):
    """Return raw source file content for the code viewer."""
    if filename not in SOURCE_FILE_MAP:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown source file: {filename}")
    rel_path, lang = SOURCE_FILE_MAP[filename]
    full_path = os.path.normpath(os.path.join(SOURCE_DIR, rel_path))
    with open(full_path, "r") as f:
        content = f.read()
    return {"filename": filename, "language": lang, "content": content}


@app.get("/api/sources")
def list_sources():
    """List all available source files grouped by type."""
    abap  = [k for k in SOURCE_FILE_MAP if k.endswith(".abap")]
    java  = [k for k in SOURCE_FILE_MAP if k.endswith(".java")]
    cmdb  = [k for k in SOURCE_FILE_MAP if "cmdb" in SOURCE_FILE_MAP[k][0]]
    sapdd = [k for k in SOURCE_FILE_MAP if "sap/dd" in SOURCE_FILE_MAP[k][0]]
    reg   = [k for k in SOURCE_FILE_MAP if "regulations" in SOURCE_FILE_MAP[k][0]]
    sp    = [k for k in SOURCE_FILE_MAP if "sharepoint" in SOURCE_FILE_MAP[k][0]]
    return {"abap": abap, "java": java, "cmdb": cmdb, "sap_dd": sapdd,
            "regulations": reg, "sharepoint": sp}


@app.get("/api/process-steps")
def list_process_steps():
    return db.query(
        """
        MATCH (s)
        WHERE s.kg = 'process' AND labels(s)[0] IN ['ProcessStep','BusinessFunction','Decision','Exception']
        RETURN s.id AS id, s.name AS name, labels(s)[0] AS type,
               s.language AS language, s.source_file AS source_file,
               s.change_required AS change_required, s.peppol_fields AS peppol_fields
        ORDER BY s.change_required DESC, s.name
        """
    )


# ── HITL Validation Endpoints ────────────────────────────────────────────────

class NodeValidationUpdate(BaseModel):
    validated_status: str                    # "confirmed" | "incorrect" | "needs_clarification"
    change_required: Optional[bool] = None
    peppol_fields: Optional[List[str]] = None
    validation_notes: Optional[str] = ""


class RelationshipCreate(BaseModel):
    from_id: str
    to_id: str
    label: str = "CALLS"


class RelationshipDelete(BaseModel):
    from_id: str
    to_id: str
    label: str = "CALLS"


@app.get("/api/validate/process")
def get_process_validation():
    """Return all process nodes with their current validation state and CALLS edges."""
    nodes = db.query(
        """
        MATCH (n)
        WHERE n.kg = 'process'
          AND labels(n)[0] IN ['ProcessStep','BusinessFunction','Decision','Exception']
        RETURN elementId(n) AS id,
               labels(n)[0] AS label,
               n.name AS name,
               n.kg AS kg,
               n.language AS language,
               n.source_file AS source_file,
               n.change_required AS change_required,
               n.peppol_fields AS peppol_fields,
               coalesce(n.validated_status, 'unreviewed') AS validated_status,
               coalesce(n.validation_notes, '') AS validation_notes,
               properties(n) AS props
        """
    )
    edges = db.query(
        """
        MATCH (a {kg: 'process'})-[r:CALLS]->(b {kg: 'process'})
        RETURN elementId(r) AS id,
               elementId(a) AS from_id,
               elementId(b) AS to_id,
               type(r) AS label
        """
    )
    return {"nodes": nodes, "edges": edges}


@app.patch("/api/validate/node/{node_id}")
def validate_node(node_id: str, body: NodeValidationUpdate):
    """Update a process node's validation state and optionally its change_required / peppol_fields."""
    set_clauses = ["n.validated_status = $status", "n.validation_notes = $notes"]
    params = {
        "node_id": node_id,
        "status": body.validated_status,
        "notes": body.validation_notes or "",
    }
    if body.change_required is not None:
        set_clauses.append("n.change_required = $change_required")
        params["change_required"] = body.change_required
    if body.peppol_fields is not None:
        set_clauses.append("n.peppol_fields = $peppol_fields")
        params["peppol_fields"] = body.peppol_fields

    result = db.write(
        f"""
        MATCH (n) WHERE elementId(n) = $node_id
        SET {', '.join(set_clauses)}
        RETURN elementId(n) AS id, n.validated_status AS validated_status,
               n.change_required AS change_required, n.peppol_fields AS peppol_fields
        """,
        **params,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return result[0]


@app.post("/api/validate/relationship")
def add_relationship(body: RelationshipCreate):
    """Add a new relationship between two process nodes (human correction)."""
    existing = db.query(
        """
        MATCH (a)-[r]->(b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id AND type(r) = $label
        RETURN count(r) AS cnt
        """,
        from_id=body.from_id, to_id=body.to_id, label=body.label,
    )
    if existing and existing[0]["cnt"] > 0:
        return {"status": "already_exists"}

    result = db.write(
        f"""
        MATCH (a), (b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id
        CREATE (a)-[r:{body.label} {{human_added: true}}]->(b)
        RETURN elementId(r) AS id, type(r) AS label
        """,
        from_id=body.from_id, to_id=body.to_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="One or both nodes not found")
    return {"status": "created", "edge": result[0]}


@app.delete("/api/validate/relationship")
def remove_relationship(body: RelationshipDelete):
    """Remove a relationship between two process nodes (human correction)."""
    result = db.write(
        """
        MATCH (a)-[r]->(b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id AND type(r) = $label
        DELETE r
        RETURN count(r) AS deleted
        """,
        from_id=body.from_id, to_id=body.to_id, label=body.label,
    )
    count = result[0]["deleted"] if result else 0
    return {"status": "deleted", "count": count}


# ── Assessment (SSE streaming) ────────────────────────────────────────────────

@app.get("/api/assess")
async def assess(
    regulation: str = Query(default="Belgium Mandatory B2B E-Invoicing"),
    country:    str = Query(default="BE"),
):
    """
    Run 5-agent RCRB assessment, streaming results via Server-Sent Events.
    Each event: {"agent": "...", "content": "..."}
    """
    async def event_generator():
        import queue
        import threading

        q: queue.Queue = queue.Queue()

        def run_sync():
            try:
                for agent_name, content in run_assessment(regulation, country):
                    q.put((agent_name, content))
            finally:
                q.put(None)  # sentinel — always signals done even on error

        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()

        while True:
            # Poll the queue in a thread so we don't block the event loop
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                break
            agent_name, content = item
            yield {"event": "agent_result",
                   "data": json.dumps({"agent": agent_name, "content": content})}

        yield {"event": "done", "data": json.dumps({"status": "complete"})}

    return EventSourceResponse(event_generator())


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    counts = db.query(
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
    )
    edge_count = db.query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
    return {"node_counts": counts, "total_edges": edge_count}


@app.post("/api/demo/reset")
def demo_reset():
    """
    Reset all HITL validation state for a clean demo run.
    Clears validated_status and validation_notes from all process nodes,
    and removes any human-added CALLS relationships.
    Does NOT touch change_required / peppol_fields (seeded data).
    """
    node_result = db.write(
        """
        MATCH (n)
        WHERE n.kg = 'process'
          AND labels(n)[0] IN ['ProcessStep','BusinessFunction','Decision','Exception']
          AND (n.validated_status IS NOT NULL OR n.validation_notes IS NOT NULL)
        REMOVE n.validated_status, n.validation_notes
        RETURN count(n) AS reset_nodes
        """
    )
    edge_result = db.write(
        """
        MATCH ()-[r:CALLS {human_added: true}]->()
        DELETE r
        RETURN count(r) AS removed_edges
        """
    )
    reset_nodes   = node_result[0]["reset_nodes"]   if node_result   else 0
    removed_edges = edge_result[0]["removed_edges"] if edge_result   else 0
    return {"status": "reset", "reset_nodes": reset_nodes, "removed_edges": removed_edges}


@app.get("/")
def health():
    return {"status": "ok", "service": "HPE AKG Platform API"}
