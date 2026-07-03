PYTHONPATH := src
export PYTHONPATH

# Container engine: auto-detect docker, else podman. Override: make up COMPOSE="podman compose"
COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker compose || echo podman compose)

demo:      ## ONE COMMAND: set up everything and launch the app + UI
	python run.py

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

install-l1: ## install Level 1 dependencies (docling)
	python -m pip install -r requirements-l1.txt

ingest:    ## Level 1: read corpus -> extract facts -> data/staging/ (full: AI prose extraction)
	python scripts/ingest.py

ingest-structured: ## Level 1 without AI (runs with only Level 0 deps)
	python scripts/ingest.py --structured-only

build-graph: ## Level 2: load staged facts into Neo4j (merge duplicates, validate links)
	python scripts/build_graph.py

install-l3: ## install Level 3 dependencies (FastAPI + uvicorn)
	python -m pip install -r requirements-l3.txt

copilot:   ## Level 3: ask the copilot (make copilot Q="Is PSV-110B overdue?")
	python scripts/copilot.py --question "$(Q)" --role "$(or $(ROLE),engineer)"

api:       ## Level 3: run the copilot API (http://localhost:8000/docs)
	uvicorn brain.api.app:app --reload --port 8000

compliance: ## Level 4a: run the compliance check + evidence package
	python scripts/compliance.py

rca:       ## Level 4b: root-cause analysis (make rca ASSET=P-101A)
	python scripts/rca.py --asset "$(or $(ASSET),P-101A)"

lessons:   ## Level 4c: recurring patterns + proactive warnings
	python scripts/lessons.py

scorecard: ## Level 5: aggregate every judged metric into one scorecard
	python eval/scorecard.py

eval:      ## run all benchmarks (extraction + copilot + compliance + rca + lessons)
	python eval/extraction_eval.py && echo "" && python eval/copilot_bench.py \
	  && echo "" && python eval/compliance_eval.py && echo "" && python eval/rca_eval.py \
	  && echo "" && python eval/lessons_eval.py

test:      ## run the regression suite (Level 0 deps only)
	python -m pytest tests/ -q

.PHONY: demo up down logs install install-l1 install-l3 init verify synth ingest \
        ingest-structured build-graph copilot api compliance rca lessons \
        scorecard eval test
