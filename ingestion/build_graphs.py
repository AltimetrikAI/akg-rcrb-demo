"""
Master ingestion script — builds all four knowledge graphs and cross-KG bridges.

Usage:
  cd /Users/mihirpanchal/Documents/hpe-rcrb-poc/ingestion
  uv run python build_graphs.py

  Or with --clear to wipe the database first:
  uv run python build_graphs.py --clear
"""
import sys
import time
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

from neo4j_client import Neo4jClient
import systems_kg
import data_kg
import entity_kg
import process_kg
import bridge_builder


def main():
    do_clear = "--clear" in sys.argv

    print("=" * 60)
    print("HPE AKG Platform — Knowledge Graph Ingestion")
    print("=" * 60)

    client = Neo4jClient()

    try:
        if do_clear:
            print("\n[Setup] Clearing all existing nodes and edges...")
            client.clear_all()

        t0 = time.time()

        # 1. Systems KG — CMDB → Application nodes and relationships
        systems_kg.build(client)

        # 2. Data KG — SAP DD → Table and Column nodes
        data_kg.build(client)

        # 3. Entity KG — Regulation text → Obligation nodes (calls Claude)
        entity_kg.build(client)

        # 4. Process KG — ABAP + Java code → ProcessStep nodes (calls Claude)
        process_kg.build(client)

        # 5. Bridge Builder — cross-KG edges connecting all four graphs
        bridge_builder.build(client)

        elapsed = time.time() - t0

        print("\n" + "=" * 60)
        print(f"Ingestion complete in {elapsed:.1f}s")
        print("Open Neo4j Browser at http://localhost:7474")
        print("Query to verify: MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC")
        print("=" * 60)

    finally:
        client.close()


if __name__ == "__main__":
    main()
