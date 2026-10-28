"""
Data KG Builder
---------------
Reads SAP Data Dictionary JSON (simulated DD02L/DD03L) and writes:
  Nodes  : Table (tabname, description, application, peppol_relevant)
           Column (fieldname, datatype, peppol_field, mandatory, change_required)
  Edges  : CONTAINS_FIELD, FLOWS_TO (table-to-table lineage based on shared keys)
"""
import json
from pathlib import Path
from neo4j_client import Neo4jClient

DATA_DIR = Path(__file__).parent.parent / "data" / "sap" / "dd"

# Tables that flow data into downstream tables via shared key fields
TABLE_LINEAGE = [
    ("VBAK", "VBRK"),   # Sales order -> Billing header
    ("VBRK", "BKPF"),   # Billing header -> FI accounting doc
    ("VBRK", "VBRP"),   # Billing header -> Billing items
    ("VBRP", "BSEG"),   # Billing item -> FI line item (tax)
    ("KNA1", "VBRK"),   # Customer master -> Billing (VAT field)
    ("T007A", "BSEG"),  # Tax key config -> Accounting segment
    ("BKPF", "BSEG"),   # FI doc header -> FI doc segment
]


def build(client: Neo4jClient):
    print("\n[Data KG] Building from SAP Data Dictionary...")

    tables = json.loads((DATA_DIR / "tables.json").read_text())
    fields = json.loads((DATA_DIR / "fields.json").read_text())

    # ── Table Nodes ──────────────────────────────────────────────────────────
    for t in tables:
        client.run(
            """
            MERGE (tbl:Table {tabname: $tabname})
            SET tbl.description      = $desc,
                tbl.application      = $app,
                tbl.peppol_relevant  = $peppol,
                tbl.regulatory_note  = $note,
                tbl.kg               = 'data'
            """,
            tabname = t["tabname"],
            desc    = t.get("ddtext", ""),
            app     = t.get("applclass", ""),
            peppol  = t.get("u_peppol_relevant", False),
            note    = t.get("u_regulatory_note", ""),
        )
        print(f"  Node  Table: {t['tabname']} — {t.get('ddtext','')}")

    # ── Column Nodes + CONTAINS_FIELD edges ──────────────────────────────────
    for f in fields:
        node_id = f"{f['tabname']}.{f['fieldname']}"
        client.run(
            """
            MERGE (col:Column {node_id: $node_id})
            SET col.tabname         = $tabname,
                col.fieldname       = $fieldname,
                col.datatype        = $dtype,
                col.length          = $leng,
                col.description     = $desc,
                col.peppol_field    = $peppol_field,
                col.be_mandatory    = $be_mandatory,
                col.change_required = $change_required,
                col.note            = $note,
                col.kg              = 'data'
            """,
            node_id         = node_id,
            tabname         = f["tabname"],
            fieldname       = f["fieldname"],
            dtype           = f.get("datatype", ""),
            leng            = f.get("leng", 0),
            desc            = f.get("ddtext", ""),
            peppol_field    = f.get("u_peppol_field"),
            be_mandatory    = f.get("u_be_mandatory", False),
            change_required = f.get("u_change_required", False),
            note            = f.get("u_note", ""),
        )
        client.run(
            """
            MATCH (tbl:Table  {tabname:  $tabname})
            MATCH (col:Column {node_id:  $node_id})
            MERGE (tbl)-[:CONTAINS_FIELD]->(col)
            """,
            tabname = f["tabname"],
            node_id = node_id,
        )

    print(f"  Columns + CONTAINS_FIELD edges: {len(fields)}")

    # ── FLOWS_TO edges (table lineage) ───────────────────────────────────────
    for src, dst in TABLE_LINEAGE:
        client.run(
            """
            MATCH (a:Table {tabname: $src})
            MATCH (b:Table {tabname: $dst})
            MERGE (a)-[:FLOWS_TO]->(b)
            """,
            src=src, dst=dst,
        )
        print(f"  Edge  FLOWS_TO: {src} -> {dst}")

    print(f"[Data KG] Done — {len(tables)} tables, {len(fields)} columns, {len(TABLE_LINEAGE)} lineage edges.")
