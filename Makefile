PYTHONPATH := src
export PYTHONPATH

# Container engine: auto-detect docker, else podman. Override: make up COMPOSE="podman compose"
COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker compose || echo podman compose)

demo:      ## ONE COMMAND: set up everything and launch the app + UI
	python run.py

logs:      ## tail service logs
	$(COMPOSE) logs -f

# ── Docker: 4 one-line commands. No file edits, except the Gemini key, which
# needs a manual edit to .env (docker compose reads it automatically from
# there — same file python run.py uses; see README.md) ─────────────────────
_wait_for_ollama = @echo "Waiting for Ollama to start..."; \
	until $(COMPOSE) exec ollama ollama list >/dev/null 2>&1; do sleep 2; done
_pull_models = $(COMPOSE) exec ollama ollama pull qwen2.5:7b && \
	$(COMPOSE) exec ollama ollama pull qwen2.5vl:7b

docker-build:  ## build the app image only — nothing started
	$(COMPOSE) build app

docker-app:    ## 1 — simple app, nothing else. Builds + starts, one command.
	$(COMPOSE) up --build -d app
	@echo "UI: http://localhost:8000/ui"

docker-ollama: ## 2 — simple app + Ollama (local LLM; models pulled automatically, ~11GB)
	LLM_PROVIDER=ollama $(COMPOSE) --profile ollama up --build -d
	$(_wait_for_ollama)
	$(_pull_models)
	$(COMPOSE) restart app
	@echo "UI: http://localhost:8000/ui   (local LLM ready, no cloud calls)"

docker-neo4j:  ## 3 — simple app + Neo4j (persisted graph, Cypher browser at :7474)
	$(COMPOSE) --profile neo4j up --build -d
	@echo "UI: http://localhost:8000/ui   Neo4j browser: http://localhost:7474"

docker-both:   ## 4 — simple app + Ollama + Neo4j together
	LLM_PROVIDER=ollama $(COMPOSE) --profile neo4j --profile ollama up --build -d
	$(_wait_for_ollama)
	$(_pull_models)
	$(COMPOSE) restart app
	@echo "UI: http://localhost:8000/ui   Neo4j: http://localhost:7474   (local LLM ready)"

docker-down:   ## stop everything started by any docker-* target
	$(COMPOSE) down

docker-demo:   ## DEV/DEMO — generate + ingest a fake sample plant into a running docker-* app
	curl -X POST http://localhost:8000/dev/seed-demo-data
	@echo "\nUI: http://localhost:8000/ui   (fake demo data loaded, isolated under data/corpus/*/demo/)"

docker-demo-undo: ## DEV/DEMO — remove exactly what docker-demo added, leaves real data untouched
	curl -X POST http://localhost:8000/dev/delete-demo-data
	@echo "\nUI: http://localhost:8000/ui   (demo data removed)"

ollama-pull: ## re-pull the local-LLM models manually (docker-ollama/docker-both already do this)
	$(_pull_models)

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

.PHONY: demo logs docker-build docker-app docker-ollama docker-neo4j docker-both \
        docker-down docker-demo docker-demo-undo ollama-pull install install-l1 \
        install-l3 init verify synth ingest ingest-structured build-graph copilot \
        api compliance rca lessons scorecard eval test
