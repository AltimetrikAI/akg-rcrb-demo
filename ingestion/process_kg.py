"""
Process KG Builder
-------------------
Reads ABAP and Java source files, sends each to Claude Sonnet for code analysis,
then writes extracted process structure to Neo4j:

  Nodes  : ProcessStep (name, type, description, language, source_file)
           Role (name)
           Decision (name, condition)
           Exception (name, error_type, peppol_field)
  Edges  : TRIGGERS, FOLLOWS, EXECUTED_BY (ProcessStep -> Application),
           CALLS (ProcessStep -> ProcessStep for function calls)
"""
import os
import json
from pathlib import Path
import anthropic
from neo4j_client import Neo4jClient

DATA_DIR = Path(__file__).parent.parent / "data"

ABAP_DIR = DATA_DIR / "sap" / "abap"
JAVA_DIR = DATA_DIR / "java" / "src"

CODE_ANALYSIS_PROMPT = """You are a SAP/Java enterprise integration architect.
Analyze the following source code and extract its process graph structure.

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{
  "process_steps": [
    {{
      "id": "unique-slug",
      "name": "Human readable step name",
      "type": "BusinessFunction|ProcessStep|Decision|Exception",
      "description": "What this step does in business terms",
      "language": "ABAP|Java",
      "source_file": "filename",
      "peppol_fields": ["BT-031", "BT-048"],
      "change_required": true,
      "change_note": "Why change is needed for Belgium e-invoicing",
      "sap_tables_read": ["VBRK", "KNA1"],
      "sap_tables_write": ["BKPF", "BSEG"]
    }}
  ],
  "calls": [
    {{"from": "step-id-1", "to": "step-id-2", "label": "optional label"}}
  ],
  "follows": [
    {{"from": "step-id-1", "to": "step-id-2"}}
  ],
  "exceptions": [
    {{"id": "exc-slug", "name": "Exception name", "peppol_field": "BT-048", "thrown_by": "step-id"}}
  ],
  "executed_by_application": "Application sys_id from CMDB (e.g. ci-001-sap-s4-emea for ABAP, ci-005-invoice-delivery-svc for Java InvoiceDeliveryService)"
}}

For ABAP code: map to CMDB application ci-001-sap-s4-emea (SAP S/4HANA EMEA PRD)
  Exception: if the ABAP calls DCP, also note the DCP application ci-002-sap-dcp

For Java code: map to the correct microservice:
  InvoiceDeliveryService  -> ci-005-invoice-delivery-svc
  CustomerVatService      -> ci-006-customer-vat-svc
  TaxDeterminationService -> ci-007-tax-determination-svc
  PeppolRouter            -> ci-005-invoice-delivery-svc (same service)
  BelgianVatValidator     -> ci-005-invoice-delivery-svc (called from CustomerVatService)

Focus on Belgium e-invoicing impact: identify every step that touches BT-031, BT-048, BT-9, BG-23, or channel routing.
Mark change_required=true where the code comment says "CHANGE REQUIRED" or where there is a gap.

SOURCE FILE: {filename}
LANGUAGE: {language}

CODE:
{code}
"""


def _analyse_file(claude: anthropic.Anthropic, filepath: Path, language: str) -> dict:
    code = filepath.read_text()
    prompt = CODE_ANALYSIS_PROMPT.format(
        filename = filepath.name,
        language = language,
        code     = code,
    )
    response = claude.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 4096,
        messages   = [{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    return json.loads(raw)


def _write_analysis(client: Neo4jClient, analysis: dict, source_label: str):
    steps = {s["id"]: s for s in analysis.get("process_steps", [])}
    app_sys_id = analysis.get("executed_by_application", "")

    # ── ProcessStep / Decision / Exception Nodes ──────────────────────────
    for step in steps.values():
        label = step.get("type", "ProcessStep")
        if label not in ("BusinessFunction", "ProcessStep", "Decision", "Exception", "Role"):
            label = "ProcessStep"
        cypher = f"""
            MERGE (s:{label} {{id: $id}})
            SET s.name            = $name,
                s.description     = $description,
                s.language        = $language,
                s.source_file     = $source_file,
                s.peppol_fields   = $peppol_fields,
                s.change_required = $change_required,
                s.change_note     = $change_note,
                s.sap_tables_read = $sap_tables_read,
                s.sap_tables_write= $sap_tables_write,
                s.kg              = 'process'
        """
        client.run(
            cypher,
            id              = step["id"],
            name            = step["name"],
            description     = step.get("description", ""),
            language        = step.get("language", ""),
            source_file     = step.get("source_file", ""),
            peppol_fields   = step.get("peppol_fields", []),
            change_required = step.get("change_required", False),
            change_note     = step.get("change_note", ""),
            sap_tables_read = step.get("sap_tables_read", []),
            sap_tables_write= step.get("sap_tables_write", []),
        )
        print(f"  Node  {label}: {step['name']}")

        # EXECUTED_BY edge to Application in Systems KG
        if app_sys_id:
            client.run(
                """
                MATCH (s {id: $step_id})
                MATCH (a:Application {sys_id: $app_id})
                MERGE (s)-[:EXECUTED_BY]->(a)
                """,
                step_id = step["id"],
                app_id  = app_sys_id,
            )

    # ── CALLS edges (within process) ─────────────────────────────────────
    for call in analysis.get("calls", []):
        client.run(
            """
            MATCH (a {id: $from_id})
            MATCH (b {id: $to_id})
            MERGE (a)-[:CALLS]->(b)
            """,
            from_id = call["from"],
            to_id   = call["to"],
        )

    # ── FOLLOWS edges ─────────────────────────────────────────────────────
    for follow in analysis.get("follows", []):
        client.run(
            """
            MATCH (a {id: $from_id})
            MATCH (b {id: $to_id})
            MERGE (a)-[:FOLLOWS]->(b)
            """,
            from_id = follow["from"],
            to_id   = follow["to"],
        )

    # ── Exception Nodes ───────────────────────────────────────────────────
    for exc in analysis.get("exceptions", []):
        client.run(
            """
            MERGE (e:Exception {id: $id})
            SET e.name         = $name,
                e.peppol_field = $peppol_field,
                e.kg           = 'process'
            """,
            id           = exc["id"],
            name         = exc["name"],
            peppol_field = exc.get("peppol_field", ""),
        )
        if exc.get("thrown_by"):
            client.run(
                """
                MATCH (s {id: $step_id})
                MATCH (e:Exception {id: $exc_id})
                MERGE (s)-[:THROWS]->(e)
                """,
                step_id = exc["thrown_by"],
                exc_id  = exc["id"],
            )


def build(client: Neo4jClient):
    print("\n[Process KG] Building from ABAP and Java source code via Claude...")

    claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    abap_files = sorted(ABAP_DIR.glob("*.abap"))
    java_files = sorted(JAVA_DIR.glob("*.java"))

    analyses = []

    for filepath in abap_files:
        print(f"\n  Analysing ABAP: {filepath.name}")
        analysis = _analyse_file(claude, filepath, "ABAP")
        analyses.append(analysis)
        _write_analysis(client, analysis, filepath.name)

    for filepath in java_files:
        print(f"\n  Analysing Java: {filepath.name}")
        analysis = _analyse_file(claude, filepath, "Java")
        analyses.append(analysis)
        _write_analysis(client, analysis, filepath.name)

    # ── FOLLOWS chain: O2C process order ─────────────────────────────────
    # Link the top-level O2C steps in business process order.
    # These IDs come from Claude's output; we create a generic O2C anchor.
    client.run(
        """
        MERGE (o2c:BusinessFunction {id: 'o2c-process-root'})
        SET o2c.name = 'Order-to-Cash (O2C) Process',
            o2c.description = 'End-to-end order-to-cash business process for EMEA',
            o2c.kg = 'process'
        """
    )

    total_steps = sum(len(a.get("process_steps", [])) for a in analyses)
    print(f"\n[Process KG] Done — {total_steps} process nodes written from {len(analyses)} source files.")
