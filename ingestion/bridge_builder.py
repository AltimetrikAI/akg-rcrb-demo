"""
Bridge Builder
--------------
Creates cross-KG edges using property-based matching (not hardcoded IDs).

  (ProcessStep)  -[:USES_TABLE]->   (Table)      — via sap_tables_read/write properties
  (Obligation)   -[:MAPS_TO]->      (Column)     — via Obligation.sap_field = tabname.fieldname
  (Obligation)   -[:GOVERNS]->      (ProcessStep) — via peppol_fields array overlap
  (Application)  -[:CONTAINS_DATA]->(Table)       — via CMDB sys_id (stable)
"""
from neo4j_client import Neo4jClient

APPLICATION_CONTAINS_DATA = [
    ("ci-001-sap-s4-emea", "VBRK"),
    ("ci-001-sap-s4-emea", "VBRP"),
    ("ci-001-sap-s4-emea", "BKPF"),
    ("ci-001-sap-s4-emea", "BSEG"),
    ("ci-001-sap-s4-emea", "T007A"),
    ("ci-001-sap-s4-emea", "TTXD"),
    ("ci-001-sap-s4-emea", "VBAK"),
    ("ci-001-sap-s4-emea", "ZHPE_EINVOICE_AUDIT"),
    ("ci-004-sap-mdg",     "KNA1"),
    ("ci-004-sap-mdg",     "LFA1"),
]


def build(client: Neo4jClient):
    print("\n[Bridge Builder] Creating cross-KG edges via property matching...")

    # ── ProcessStep -[:USES_TABLE]-> Table  (read) ────────────────────────
    r = client.run("""
        MATCH (s), (t:Table)
        WHERE s.kg = 'process'
          AND t.tabname IN s.sap_tables_read
          AND s.sap_tables_read IS NOT NULL
        MERGE (s)-[:USES_TABLE {access: 'READS'}]->(t)
        RETURN count(*) AS c
    """)
    read_count = r[0]["c"] if r else 0

    r = client.run("""
        MATCH (s), (t:Table)
        WHERE s.kg = 'process'
          AND t.tabname IN s.sap_tables_write
          AND s.sap_tables_write IS NOT NULL
        MERGE (s)-[:USES_TABLE {access: 'WRITES'}]->(t)
        RETURN count(*) AS c
    """)
    write_count = r[0]["c"] if r else 0
    print(f"  {read_count + write_count} ProcessStep -[:USES_TABLE]-> Table edges (reads+writes)")

    # ── Obligation -[:MAPS_TO]-> Column  ─────────────────────────────────
    # Obligation.sap_field format: "VBRK.STCEG" → split on dot
    r = client.run("""
        MATCH (o:Obligation), (c:Column)
        WHERE o.sap_field IS NOT NULL
          AND c.node_id = o.sap_field
        MERGE (o)-[:MAPS_TO]->(c)
        RETURN count(*) AS c
    """)
    maps_count = r[0]["c"] if r else 0

    # Also match BG-23 which governs multiple BSEG fields
    r2 = client.run("""
        MATCH (o:Obligation {bt_field: 'BG-23'}), (c:Column)
        WHERE c.peppol_field IN ['BG-23-key', 'BT-116', 'BT-117', 'BT-119']
        MERGE (o)-[:MAPS_TO]->(c)
        RETURN count(*) AS c
    """)
    maps_count += r2[0]["c"] if r2 else 0
    print(f"  {maps_count} Obligation -[:MAPS_TO]-> Column edges")

    # ── Obligation -[:GOVERNS]-> ProcessStep  ────────────────────────────
    # Match via peppol_fields array: any node whose peppol_fields contains the BT field
    r = client.run("""
        MATCH (o:Obligation), (s)
        WHERE s.kg = 'process'
          AND s.peppol_fields IS NOT NULL
          AND o.bt_field IN s.peppol_fields
        MERGE (o)-[:GOVERNS]->(s)
        RETURN count(*) AS c
    """)
    governs_peppol = r[0]["c"] if r else 0

    # Also match via change_required steps that mention the BT field in change_note
    r = client.run("""
        MATCH (o:Obligation), (s)
        WHERE s.kg = 'process'
          AND s.change_required = true
          AND s.change_note IS NOT NULL
          AND s.change_note CONTAINS o.bt_field
        MERGE (o)-[:GOVERNS]->(s)
        RETURN count(*) AS c
    """)
    governs_note = r[0]["c"] if r else 0
    print(f"  {governs_peppol + governs_note} Obligation -[:GOVERNS]-> ProcessStep edges")

    # ── Application -[:CONTAINS_DATA]-> Table  ───────────────────────────
    count = 0
    for app_id, tabname in APPLICATION_CONTAINS_DATA:
        client.run("""
            MATCH (a:Application {sys_id: $app_id})
            MATCH (t:Table {tabname: $tabname})
            MERGE (a)-[:CONTAINS_DATA]->(t)
        """, app_id=app_id, tabname=tabname)
        count += 1
    print(f"  {count} Application -[:CONTAINS_DATA]-> Table edges")

    # ── Verify ────────────────────────────────────────────────────────────
    totals = client.run("MATCH ()-[r]->() RETURN count(r) AS total")
    print(f"[Bridge Builder] Done. Total edges in graph: {totals[0]['total']}")
