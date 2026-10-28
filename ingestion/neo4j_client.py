import os
from neo4j import GraphDatabase

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "hpe-rcrb-2024")


class Neo4jClient:
    def __init__(self):
        self._driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self._driver.close()

    def run(self, cypher: str, **params):
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return result.data()

    def run_many(self, statements: list[tuple[str, dict]]):
        """Execute multiple (cypher, params) pairs in one session."""
        with self._driver.session() as session:
            for cypher, params in statements:
                session.run(cypher, **params)

    def clear_all(self):
        self.run("MATCH (n) DETACH DELETE n")
        print("  Neo4j: all nodes and edges cleared.")
