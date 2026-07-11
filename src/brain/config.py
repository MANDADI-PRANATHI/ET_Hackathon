"""Central configuration. Reads from environment / .env (see .env.example)."""
from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- the "brain": one-setting switch -> "gemini" | "ollama" ---
    llm_provider: str = "gemini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_vision_model: str = "qwen2.5vl:7b"

    # --- vector index dimension (schema-only stub for a future Neo4j-backed
    # semantic search path; the current retrieval path is plain keyword search
    # and does not require this or any local ML model) ---
    embed_dim: int = 768

    # --- Neo4j (connections store: graph + vector index) ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"

    # --- document parsing ---
    docling_ocr: bool = False   # OCR off by default (born-digital PDFs); scans use the vision path

    # --- ontology profile (swap to change industry) ---
    ontology_profile: str = "config/ontology/oil_and_gas.yaml"


settings = Settings()
