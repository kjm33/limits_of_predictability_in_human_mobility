# Makefile — one-command wrappers for this repo (full details in AGENTS.md).
#
# Demo webpage (static scrollytelling):
#   make demo-serve    build everything, then serve on the LAN (Ctrl+C to stop)
#   make demo-dev      dev server with hot reload, LAN-accessible
#   make demo-data     rebuild demo/public/data.json from data/processed/ parquets
#   make demo-build    production build into demo/dist/
#
# Checks (see AGENTS.md "Definition of done"):
#   make test          full pytest suite (synthetic data only)
#   make lint          ruff check src tests scripts
#
# Override the serving port:  make demo-serve PORT=8000

PYTHON := uv run
DEMO_DIR := demo
DEMO_DATA := $(DEMO_DIR)/public/data.json
PORT ?= 4173

.PHONY: help demo-data demo-install demo-build demo-serve demo-dev test lint

help: ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

demo-data: ## rebuild demo/public/data.json from parquets
	$(PYTHON) python scripts/build_demo.py

$(DEMO_DATA):
	$(PYTHON) python scripts/build_demo.py

demo-install: ## install demo npm deps (no-op when node_modules exists)
	@command -v node >/dev/null 2>&1 || { echo "error: Node.js >= 20 required — https://nodejs.org"; exit 1; }
	test -d $(DEMO_DIR)/node_modules || (cd $(DEMO_DIR) && npm install)

demo-build: $(DEMO_DATA) demo-install ## production build into demo/dist/
	cd $(DEMO_DIR) && npm run build

demo-serve: demo-build ## serve the built site on the LAN (default port 4173)
	@echo ""
	@echo "  Serving on your LAN — open from any device on the same network:"
	@echo "    http://$$(hostname -I | awk '{print $$1}'):$(PORT)"
	@echo "  (Ctrl+C to stop; port busy? try: make demo-serve PORT=8000)"
	@echo ""
	cd $(DEMO_DIR) && npm run preview -- --host --strictPort --port $(PORT)

demo-dev: $(DEMO_DATA) demo-install ## dev server (hot reload), LAN-accessible
	@echo "  Dev server (hot reload): http://$$(hostname -I | awk '{print $$1}'):5173"
	cd $(DEMO_DIR) && npm run dev -- --host

test: ## full pytest suite (synthetic data only)
	$(PYTHON) pytest -q

lint: ## ruff check src tests scripts
	$(PYTHON) ruff check src tests scripts
