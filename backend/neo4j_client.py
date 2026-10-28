import os
from neo4j import GraphDatabase

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "hpe-rcrb-2024")

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def query(cypher: str, **params) -> list[dict]:
    with get_driver().session() as session:
        result = session.run(cypher, **params)
        return result.data()


def write(cypher: str, **params) -> list[dict]:
    with get_driver().session() as session:
        result = session.run(cypher, **params)
        return result.data()
