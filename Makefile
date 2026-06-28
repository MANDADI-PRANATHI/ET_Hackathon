PYTHONPATH := src
export PYTHONPATH

# Container engine: auto-detect docker, else podman. Override: make up COMPOSE="podman compose"
COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker compose || echo podman compose)

up:        ## start Neo4j, Postgres, MinIO (docker or podman — same compose file)
	$(COMPOSE) up -d

down:      ## stop the services
	$(COMPOSE) down

logs:      ## tail service logs
	$(COMPOSE) logs -f

install:   ## install Level 0 Python dependencies
	python -m pip install -r requirements-l0.txt

init:      ## create Neo4j constraints + vector index from the ontology
	python -m brain.stores.neo4j_init

verify:    ## health-check all services + the LLM provider
	python scripts/verify_setup.py

synth:     ## generate synthetic work orders / inspections / permits / NCRs
	python scripts/generate_synthetic.py

install-l1: ## install Level 1 dependencies (docling + embeddings)
	python -m pip install -r requirements-l1.txt

ingest:    ## Level 1: read corpus -> extract facts -> data/staging/ (full: AI + embeddings)
	python scripts/ingest.py

ingest-structured: ## Level 1 without AI/embeddings (runs with only Level 0 deps)
	python scripts/ingest.py --structured-only

build-graph: ## Level 2: load staged facts into Neo4j (merge duplicates, validate links)
	python scripts/build_graph.py

ask:       ## Level 3a: ask the copilot — make ask Q="your question"
	python scripts/ask.py "$(Q)"

.PHONY: up down logs install install-l1 init verify synth ingest ingest-structured build-graph ask
