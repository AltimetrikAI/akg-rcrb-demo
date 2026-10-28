"""
Business Entity KG Builder
---------------------------
Reads regulation text + SharePoint RCRB docs, calls Claude to extract:
  Nodes  : Obligation (bt_field, description, mandatory, change_required)
           Regulation (name, effective_date, country)
           BusinessEntity (name, type)  -- HPE legal entities
  Edges  : REQUIRES (Regulation -> Obligation)
           GOVERNS  (Regulation -> BusinessEntity)
           MAPS_TO  (Obligation -> Column) -- written by bridge_builder
"""
import os
from pathlib import Path
import anthropic
from neo4j_client import Neo4jClient

DATA_DIR = Path(__file__).parent.parent / "data"


def build(client: Neo4jClient):
    print("\n[Entity KG] Building from regulation text + SharePoint docs...")

    reg_text   = (DATA_DIR / "regulations" / "belgium_einvoicing.txt").read_text()
    prior_rcrb = (DATA_DIR / "sharepoint" / "RCRB-2023-France-eInvoice.md").read_text()
    policy     = (DATA_DIR / "sharepoint" / "HPE-eInvoice-Policy.md").read_text()

    claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are analyzing regulatory documents for a knowledge graph.

Extract structured information from the Belgium e-invoicing regulation below.

Return ONLY valid JSON with this exact structure:
{{
  "regulation": {{
    "name": "Belgium Mandatory B2B E-Invoicing",
    "legal_basis": "Royal Decree 9 March 2022 / EU Directive 2014/55/EU",
    "effective_date": "2026-01-01",
    "country": "BE",
    "format": "Peppol BIS 3.0 (UBL 2.1)",
    "channel": "Peppol AS4"
  }},
  "obligations": [
    {{
      "id": "OBL-BT-031",
      "bt_field": "BT-031",
      "name": "Seller VAT Identifier",
      "description": "VAT registration number of the seller",
      "mandatory": true,
      "change_required": false,
      "gap_description": "No gap — already present in VBRK.STCEG",
      "impact_level": "LOW",
      "sap_field": "VBRK.STCEG"
    }}
  ],
  "hpe_entities": [
    {{"name": "HPE EMEA BE10", "country": "BE", "type": "LegalEntity"}},
    {{"name": "HPE EMEA BE20", "country": "BE", "type": "LegalEntity"}}
  ]
}}

Include obligations for: BT-031, BT-048, BT-9, BG-23, FORMAT, CHANNEL, BT-5.
For each obligation include the gap_description from the regulation and impact_level (HIGH/MEDIUM/LOW).

REGULATION TEXT:
{reg_text}

PRIOR RCRB CONTEXT (France 2023 — for gap pattern recognition):
{prior_rcrb[:2000]}

HPE POLICY (for entity extraction):
{policy[:1500]}
"""

    print("  Calling Claude to extract Entity KG structure...")
    response = claude.messages.create(
        model     = "claude-sonnet-4-6",
        max_tokens= 2048,
        messages  = [{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]

    import json
    data = json.loads(raw)

    # ── Regulation Node ──────────────────────────────────────────────────────
    reg = data["regulation"]
    client.run(
        """
        MERGE (r:Regulation {name: $name, country: $country})
        SET r.legal_basis     = $legal_basis,
            r.effective_date  = $effective_date,
            r.format          = $format,
            r.channel         = $channel,
            r.kg              = 'entity'
        """,
        **reg,
    )
    print(f"  Node  Regulation: {reg['name']}")

    # ── Obligation Nodes + REQUIRES edges ────────────────────────────────────
    for obl in data["obligations"]:
        client.run(
            """
            MERGE (o:Obligation {id: $id})
            SET o.bt_field        = $bt_field,
                o.name            = $name,
                o.description     = $description,
                o.mandatory       = $mandatory,
                o.change_required = $change_required,
                o.gap_description = $gap_description,
                o.impact_level    = $impact_level,
                o.sap_field       = $sap_field,
                o.kg              = 'entity'
            """,
            **obl,
        )
        client.run(
            """
            MATCH (r:Regulation {name: $reg_name})
            MATCH (o:Obligation  {id: $obl_id})
            MERGE (r)-[:REQUIRES]->(o)
            """,
            reg_name = reg["name"],
            obl_id   = obl["id"],
        )
        print(f"  Node  Obligation: {obl['bt_field']} — {obl['name']} [{obl['impact_level']}]")

    # ── Business Entity Nodes + GOVERNS edges ────────────────────────────────
    for ent in data.get("hpe_entities", []):
        client.run(
            """
            MERGE (e:BusinessEntity {name: $name})
            SET e.country = $country,
                e.type    = $type,
                e.kg      = 'entity'
            """,
            **ent,
        )
        client.run(
            """
            MATCH (r:Regulation   {name: $reg_name})
            MATCH (e:BusinessEntity {name: $ent_name})
            MERGE (r)-[:GOVERNS]->(e)
            """,
            reg_name = reg["name"],
            ent_name = ent["name"],
        )
        print(f"  Node  BusinessEntity: {ent['name']}")

    print(f"[Entity KG] Done — {len(data['obligations'])} obligations, {len(data.get('hpe_entities', []))} entities.")
