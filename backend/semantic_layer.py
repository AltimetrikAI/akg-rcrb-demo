"""
Semantic Layer for Regulatory Impact Assessment
-------------------------------------------------
Named query functions and business concept definitions.
Agents call these instead of writing raw Cypher so that:
  1. Business terms (readiness_score, critical_blocker) are defined once.
  2. Agents receive pre-structured context and focus on interpretation.
  3. Query logic lives here, not scattered across prompt strings.

Definitions are stored in CONFIG (below) and can be updated at runtime
via the /api/semantic/config endpoints — no restart needed.
"""
import neo4j_client as db


# ── Editable Configuration ────────────────────────────────────────────────────
# This is the semantic layer's "vocabulary". Change these to redefine what
# terms mean for a specific customer or regulatory context.

CONFIG = {
    "impact_levels": {
        "HIGH":   "Blocks invoice transmission entirely if not resolved before go-live",
        "MEDIUM": "Required for full compliance but invoice may still transmit",
        "LOW":    "Informational; no immediate compliance risk at go-live",
    },
    "readiness_thresholds": [
        {"label": "NOT_READY",  "min": 0,  "max": 40},
        {"label": "AT_RISK",    "min": 40, "max": 70},
        {"label": "NEAR_READY", "min": 70, "max": 90},
        {"label": "READY",      "min": 90, "max": 101},
    ],
    "change_types": {
        "Code Change":   "ABAP function module or Java class must be modified",
        "Config Change": "Customizing table (IMG) or configuration parameter must be updated",
        "MDG Workflow":  "Master Data Governance validation rule or workflow must be added",
        "Registration":  "External registration with a Peppol access point provider required",
    },
    "critical_blocker_rule": {
        "impact_levels": ["HIGH"],
        "description": "An obligation that, if unresolved, will prevent invoice transmission at go-live.",
    },
}

# Convenience aliases so agents.py doesn't need to dig into CONFIG
IMPACT_LEVELS         = CONFIG["impact_levels"]
READINESS_THRESHOLDS  = [(t["label"], t["min"], t["max"]) for t in CONFIG["readiness_thresholds"]]
CHANGE_TYPE_DEFINITIONS = CONFIG["change_types"]


# ── Named Queries ──────────────────────────────────────────────────────────────

def get_config() -> dict:
    """Return the current semantic layer configuration (for the UI editor)."""
    return CONFIG


def update_config(updates: dict) -> dict:
    """
    Apply partial updates to the semantic layer config.
    Supported keys: impact_levels, readiness_thresholds, change_types, critical_blocker_rule.
    Updates the global CONFIG and refreshes convenience aliases.
    """
    global CONFIG, IMPACT_LEVELS, READINESS_THRESHOLDS, CHANGE_TYPE_DEFINITIONS
    for key, value in updates.items():
        if key in CONFIG:
            CONFIG[key] = value
    IMPACT_LEVELS           = CONFIG["impact_levels"]
    READINESS_THRESHOLDS    = [(t["label"], t["min"], t["max"]) for t in CONFIG["readiness_thresholds"]]
    CHANGE_TYPE_DEFINITIONS = CONFIG["change_types"]
    return CONFIG


def get_critical_blockers(country: str = "BE") -> list[dict]:
    """
    Obligations that, if unresolved, will block invoice transmission.
    Uses CONFIG["critical_blocker_rule"]["impact_levels"] — editable at runtime.
    """
    levels = CONFIG["critical_blocker_rule"]["impact_levels"]
    level_list = " OR ".join([f"o.impact_level = '{lv}'" for lv in levels])
    return db.query(
        f"""
        MATCH (r:Regulation {{country: $country}})-[:REQUIRES]->(o:Obligation)
        WHERE ({level_list}) AND o.change_required = true
          AND (o.validation_status IS NULL OR o.validation_status <> 'confirmed')
        RETURN o.bt_field AS field, o.name AS name, o.gap_description AS gap,
               o.sap_field AS sap_field, o.impact_level AS impact_level,
               o.validation_status AS status
        ORDER BY o.impact_level DESC, o.name
        """,
        country=country,
    )


def get_compliance_summary(country: str = "BE") -> dict:
    """
    Headline compliance metrics: readiness score (0–100), status label, counts.
    """
    results = db.query("""
        MATCH (r:Regulation {country: $country})-[:REQUIRES]->(o:Obligation)
        RETURN
            count(o)                                                          AS total,
            sum(CASE WHEN o.change_required = true THEN 1 ELSE 0 END)        AS need_change,
            sum(CASE WHEN o.validation_status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
            sum(CASE WHEN o.impact_level = 'HIGH'
                          AND o.change_required = true
                          AND (o.validation_status IS NULL
                               OR o.validation_status <> 'confirmed')
                     THEN 1 ELSE 0 END)                                       AS critical_blockers
    """, country=country)

    if not results:
        return {
            "total_obligations": 0, "need_change": 0, "confirmed": 0,
            "critical_blockers": 0, "readiness_score": 0, "status": "UNKNOWN",
        }

    r = results[0]
    need_change = r["need_change"] or 0
    confirmed   = r["confirmed"]   or 0
    score = int((confirmed / max(need_change, 1)) * 100) if need_change > 0 else 100

    status = "NOT_READY"
    for label, lo, hi in READINESS_THRESHOLDS:
        if lo <= score < hi:
            status = label
            break

    return {
        "total_obligations": r["total"],
        "need_change":        need_change,
        "confirmed":          confirmed,
        "critical_blockers":  r["critical_blockers"],
        "readiness_score":    score,
        "status":             status,
    }


def get_all_obligations(country: str = "BE") -> list[dict]:
    """All obligations ordered by impact level — used by Regulation Agent."""
    return db.query("""
        MATCH (r:Regulation {country: $country})-[:REQUIRES]->(o:Obligation)
        RETURN o.bt_field AS field, o.name AS name, o.description AS description,
               o.mandatory AS mandatory, o.change_required AS change_required,
               o.gap_description AS gap, o.impact_level AS impact_level,
               o.sap_field AS sap_field
        ORDER BY
            CASE o.impact_level WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END,
            o.change_required DESC
    """, country=country)


def get_impacted_process_steps() -> list[dict]:
    """
    Process steps (ABAP/Java) that require code changes.
    Returns business-friendly names, technology, and the Peppol fields each step must handle.
    """
    return db.query("""
        MATCH (s)
        WHERE s.kg = 'process'
          AND (s.change_required = true
               OR (s.peppol_fields IS NOT NULL AND size(s.peppol_fields) > 0))
        OPTIONAL MATCH (o:Obligation)-[:GOVERNS]->(s)
        RETURN DISTINCT
            s.name            AS step_name,
            s.language        AS technology,
            s.source_file     AS source_file,
            s.change_note     AS change_description,
            s.change_required AS change_required,
            s.peppol_fields   AS peppol_fields,
            collect(o.bt_field + ': ' + o.name) AS governing_obligations
        ORDER BY s.change_required DESC, s.language, s.name
        LIMIT 40
    """)


def get_impacted_systems() -> list[dict]:
    """
    IT applications that own impacted process steps.
    Returns system name, tier, owner, and which components are affected.
    """
    return db.query("""
        MATCH (s)-[:EXECUTED_BY]->(a:Application)
        WHERE s.kg = 'process' AND s.change_required = true
        WITH DISTINCT a, collect(DISTINCT s.name) AS impacted_steps
        RETURN a.name AS system_name, a.tier AS tier, a.owner AS owner,
               impacted_steps
        ORDER BY a.tier, a.name
    """)


def get_data_gaps(country: str = "BE") -> list[dict]:
    """
    SAP data fields that must be populated or restructured for regulatory compliance.
    """
    return db.query("""
        MATCH (c:Column)
        WHERE c.be_mandatory = true OR c.change_required = true
        OPTIONAL MATCH (o:Obligation)-[:MAPS_TO]->(c)
        RETURN
            COALESCE(o.bt_field, c.peppol_field)   AS peppol_bt_code,
            COALESCE(o.name, c.description)         AS business_meaning,
            c.tabname     AS sap_table,
            c.fieldname   AS sap_field,
            c.description AS field_description,
            c.note        AS remediation_action,
            c.change_required AS requires_change
        ORDER BY c.change_required DESC, c.tabname, c.fieldname
    """)


# ── Context Formatters ────────────────────────────────────────────────────────
# Convert query results to clean, business-focused strings for agent prompts.
# Agents see named concepts, not raw property bags.

def format_compliance_summary(s: dict) -> str:
    return (
        f"Readiness: {s['readiness_score']}/100 — {s['status']}\n"
        f"  {s['total_obligations']} total obligations | "
        f"{s['need_change']} require changes | "
        f"{s['confirmed']} confirmed complete\n"
        f"  Critical blockers still outstanding: {s['critical_blockers']}"
    )


def format_critical_blockers(blockers: list[dict]) -> str:
    if not blockers:
        return "No unresolved critical blockers — all HIGH impact obligations addressed."
    lines = []
    for b in blockers:
        sap = f" (maps to SAP field: {b['sap_field']})" if b.get("sap_field") else ""
        lines.append(f"[BLOCKER] {b['field']} — {b['name']}{sap}\n  Current gap: {b['gap']}")
    return "\n".join(lines)


def format_obligations(obligations: list[dict]) -> str:
    lines = []
    for o in obligations:
        priority = "[P1-BLOCKER]" if (o["impact_level"] == "HIGH" and o["change_required"]) else \
                   "[P2-REQUIRED]" if o["change_required"] else "[P3-INFO]"
        sap = f", SAP: {o['sap_field']}" if o.get("sap_field") else ""
        lines.append(f"{priority} {o['field']} — {o['name']}{sap}: {o['gap']}")
    return "\n".join(lines)


def format_process_steps(steps: list[dict]) -> str:
    lines = []
    for s in steps:
        fields = ", ".join(s.get("peppol_fields") or [])
        obligations = "; ".join(s.get("governing_obligations") or [])
        priority = "[CHANGE REQUIRED]" if s["change_required"] else "[REVIEW]"
        lines.append(
            f"{priority} [{s['technology']}] {s['step_name']}"
            + (f" — Peppol fields: {fields}" if fields else "")
            + (f"\n  Obligation: {obligations}" if obligations else "")
            + (f"\n  What to change: {s['change_description']}" if s.get("change_description") else "")
        )
    return "\n".join(lines)


def format_systems(systems: list[dict]) -> str:
    lines = []
    for s in systems:
        steps = ", ".join(s.get("impacted_steps") or [])
        lines.append(
            f"{s['system_name']} [{s['tier']}] — Owner: {s['owner']}"
            + (f"\n  Affected components: {steps}" if steps else "")
        )
    return "\n".join(lines)


def format_data_gaps(fields: list[dict]) -> str:
    lines = []
    for f in fields:
        action = f"\n  Action required: {f['remediation_action']}" if f.get("remediation_action") else ""
        lines.append(
            f"{f['peppol_bt_code']} ({f['business_meaning']}): "
            f"{f['sap_table']}.{f['sap_field']} — {f['field_description']}"
            + action
        )
    return "\n".join(lines)
