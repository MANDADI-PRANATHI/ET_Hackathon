PYTHONPATH := src
export PYTHONPATH

# Container engine: auto-detect docker, else podman. Override: make up COMPOSE="podman compose"
COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker compose || echo podman compose)

demo:      ## ONE COMMAND: set up everything and launch the app + UI
	python run.py

logs:      ## tail service logs
	$(COMPOSE) logs -f

# ── Docker: four addons, everything off (false) unless you ask for it ───────
# Use ONE of these for a single need, or see README.md "Combining addons" for
# the raw docker compose commands to turn on more than one at once.
docker-build:  ## build the app image only — nothing started
	$(COMPOSE) build app

docker-app:    ## app only, no addons — the default, use this unless you need one below
	$(COMPOSE) up app -d
	@echo "UI: http://localhost:8000/ui"

docker-neo4j:  ## + Neo4j — persisted graph, Cypher browser at :7474
	$(COMPOSE) --profile neo4j up -d
	@echo "UI: http://localhost:8000/ui   Neo4j browser: http://localhost:7474"

docker-ollama: ## + Ollama — fully local LLM (run ollama-pull after this)
	$(COMPOSE) --profile ollama up -d
	@echo "UI: http://localhost:8000/ui   Now run: make ollama-pull"

docker-pdf:    ## + Docling — read real PDF/Word files (heavier build: torch, several GB)
	INSTALL_PDF=true $(COMPOSE) build app
	INSTALL_PDF=true $(COMPOSE) up app -d
	@echo "UI: http://localhost:8000/ui   (PDF/Word reading enabled)"

docker-down:   ## stop everything started by any docker-* target
	$(COMPOSE) down

ollama-pull: ## pull the local-LLM models into the running ollama container
             ## (several GB — only run this when you actually want it; never automatic)
	$(COMPOSE) exec ollama ollama pull qwen2.5:7b
	$(COMPOSE) exec ollama ollama pull qwen2.5vl:7b
	@echo "Now set LLM_PROVIDER=ollama in .env and: $(COMPOSE) restart app"

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

.PHONY: demo logs docker-build docker-app docker-neo4j docker-ollama docker-pdf \
        docker-down ollama-pull install install-l1 install-l3 init verify synth \
        ingest ingest-structured build-graph copilot api compliance rca lessons \
        scorecard eval test
