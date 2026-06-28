"""Create the Neo4j schema from the ontology: uniqueness constraints + a vector
index on Chunk.embedding (so meaning-search lives inside Neo4j for the hackathon).

Run with:  make init   (or:  PYTHONPATH=src python -m brain.stores.neo4j_init)
"""
from __future__ import annotations

from neo4j import GraphDatabase

from brain.config import settings
from brain.ontology import load_ontology


def init_schema() -> None:
    onto = load_ontology()
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    created = []
    with driver.session() as session:
        # Uniqueness constraint per node type with a declared key.
        for node in onto["nodes"]:
            label = node["label"]
            key = node.get("key")
            if not key:
                continue
            # Labels/keys come from our own trusted YAML, so f-string is safe here
            # (Cypher cannot parameterise labels/property keys).
            session.run(
                f"CREATE CONSTRAINT IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.`{key}` IS UNIQUE"
            )
            created.append(f"{label}.{key} (unique)")

        # Vector index for meaning-search over document passages.
        session.run(
            "CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.embedding) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {settings.embed_dim}, "
            "`vector.similarity_function`: 'cosine'}}"
        )
        created.append(f"Chunk.embedding (vector index, dim={settings.embed_dim})")

    driver.close()
    print("Neo4j schema ready:")
    for item in created:
        print(f"  - {item}")


if __name__ == "__main__":
    init_schema()
