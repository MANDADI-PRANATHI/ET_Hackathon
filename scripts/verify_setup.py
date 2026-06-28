"""Level 0 health-check: ontology + Neo4j + Postgres + MinIO + the LLM provider.

Run with:  make verify   (or:  python scripts/verify_setup.py)
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.config import settings  # noqa: E402


def _check(name, fn) -> bool:
    try:
        msg = fn()
        print(f"  [PASS] {name}: {msg}")
        return True
    except Exception as e:  # noqa: BLE001 - we want every failure reported, not raised
        print(f"  [FAIL] {name}: {e}")
        return False


def check_ontology() -> str:
    from brain.ontology import load_ontology, node_labels

    onto = load_ontology()
    return (
        f"{onto['profile']} — {len(node_labels(onto))} node types, "
        f"{len(onto['relationships'])} relationship types"
    )


def check_neo4j() -> str:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    driver.verify_connectivity()
    driver.close()
    return f"connected at {settings.neo4j_uri}"


def check_postgres() -> str:
    import psycopg

    with psycopg.connect(settings.postgres_dsn, connect_timeout=5) as conn:
        conn.execute("SELECT 1")
    return "connected"


def check_minio() -> str:
    from minio import Minio

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    return f"bucket '{settings.minio_bucket}' ready"


def check_llm() -> str:
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        raise RuntimeError("no GEMINI_API_KEY (set it, or use LLM_PROVIDER=ollama)")
    from brain.providers.llm import get_llm

    out = get_llm().generate("Reply with the single word: ready")
    return f"{settings.llm_provider} responded {out[:40]!r}"


def main() -> None:
    print(f"Verifying Level 0 setup (LLM provider = {settings.llm_provider})\n")
    results = [
        _check("Ontology profile", check_ontology),
        _check("Neo4j", check_neo4j),
        _check("Postgres", check_postgres),
        _check("MinIO", check_minio),
        _check("LLM provider", check_llm),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
