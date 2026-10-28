"""
Systems KG Builder
------------------
Reads ServiceNow CMDB JSON (simulated REST API response) and writes:
  Nodes  : Application (name, sys_id, owner, tier, hosting, language)
  Edges  : CALLS, DEPENDS_ON, DOWNSTREAM_OF, READS_FROM, OWNED_BY
"""
import json
from pathlib import Path
from neo4j_client import Neo4jClient

DATA_DIR = Path(__file__).parent.parent / "data" / "cmdb"


def build(client: Neo4jClient):
    print("\n[Systems KG] Building from ServiceNow CMDB...")

    ci_path  = DATA_DIR / "servicenow_cmdb_ci.json"
    rel_path = DATA_DIR / "servicenow_cmdb_rel.json"

    cis  = json.loads(ci_path.read_text())["result"]
    rels = json.loads(rel_path.read_text())["result"]

    # ── Nodes ────────────────────────────────────────────────────────────────
    for ci in cis:
        client.run(
            """
            MERGE (a:Application {sys_id: $sys_id})
            SET a.name        = $name,
                a.vendor      = $vendor,
                a.version     = $version,
                a.description = $desc,
                a.owner       = $owner,
                a.tier        = $tier,
                a.hosting     = $hosting,
                a.language    = $lang,
                a.kg          = 'systems'
            """,
            sys_id  = ci["sys_id"],
            name    = ci["name"],
            vendor  = ci.get("vendor", ""),
            version = ci.get("version", ""),
            desc    = ci.get("short_description", ""),
            owner   = ci.get("u_application_owner", ""),
            tier    = ci.get("u_tier", ""),
            hosting = ci.get("u_hosting", ""),
            lang    = ci.get("u_language", ""),
        )
        print(f"  Node  Application: {ci['name']}")

    # ── Edges ────────────────────────────────────────────────────────────────
    label_map = {
        "CALLS":       "CALLS",
        "DEPENDS_ON":  "DEPENDS_ON",
        "DOWNSTREAM_OF": "DOWNSTREAM_OF",
        "READS_FROM":  "READS_FROM",
    }

    for rel in rels:
        edge_type = label_map.get(rel.get("u_relation_label", ""), "DEPENDS_ON")
        cypher = f"""
            MATCH (a:Application {{sys_id: $parent_id}})
            MATCH (b:Application {{sys_id: $child_id}})
            MERGE (a)-[:{edge_type}]->(b)
        """
        client.run(
            cypher,
            parent_id = rel["parent"]["value"],
            child_id  = rel["child"]["value"],
        )
        print(f"  Edge  {rel['parent']['display_value']} -[{edge_type}]-> {rel['child']['display_value']}")

    print(f"[Systems KG] Done — {len(cis)} applications, {len(rels)} relationships.")
