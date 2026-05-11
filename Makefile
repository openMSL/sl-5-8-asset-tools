# Makefile for sl-5-8-asset-tools
# Build command center for common development tasks

# Allow parent makefiles to override the venv path/tooling.
VENV ?= .venv
OMB  := submodules/ontology-management-base
WIZARD_DIR := submodules/sd-creation-wizard
GIT  ?= git

# Load .env for wizard ports
-include .env
WIZARD_API_PORT      ?= 3007
WIZARD_FRONTEND_PORT ?= 5174

# OS detection for cross-platform support (Windows vs Unix)
ifeq ($(OS),Windows_NT)
    SHELL            := sh
    VENV_BIN         := $(VENV)/Scripts
    PYTHON           ?= $(VENV_BIN)/python.exe
    BOOTSTRAP_PYTHON ?= python
    ACTIVATE_SCRIPT  := $(VENV_BIN)/activate
    ACTIVATE_HINT    := use the activation script under $(VENV_BIN) for your shell
else
    VENV_BIN         := $(VENV)/bin
    PYTHON           ?= $(VENV_BIN)/python3
    BOOTSTRAP_PYTHON ?= python3
    ACTIVATE_SCRIPT  := $(VENV_BIN)/activate
    ACTIVATE_HINT    := source $(ACTIVATE_SCRIPT)
endif

PY_FILES := $(shell git ls-files '*.py')

# ── Subcommand support ───────────────────────────────────────────────
# Enables:  make generate opendrive,  make check format
SUBCMD = $(word 2,$(MAKECMDGOALS))

# Allow parent makefiles to pass pipeline flags (e.g., -enable / -disable modules).
PIPELINE_FLAGS ?=

# WIZARD=true enables the interactive metadata wizard during pipeline runs.
# Exports WIZARD_ENABLED env var which wizard_caller checks at runtime.
ifdef WIZARD
export WIZARD_ENABLED := true
endif

# Example directory mapping for `make generate <example>`
EXAMPLE_opendrive    := OpenDRIVE
EXAMPLE_openscenario := OpenSCENARIO

# ── Guards ───────────────────────────────────────────────────────────
define check_dev_setup
	@if [ ! -f "$(PYTHON)" ]; then \
		echo ""; \
		echo "[ERR] Development environment not set up."; \
		echo "  Run:  make setup"; \
		echo ""; \
		exit 1; \
	fi
endef

.PHONY: all setup install lint format check validate generate clean wizard help

# Default target
all: check

# ── Setup & Install ──────────────────────────────────────────────────

setup:
ifeq ($(SUBCMD),wizard)
	@if ! command -v node >/dev/null 2>&1; then \
		echo "[ERR] Node.js is required for the wizard. Install Node.js 20+ first."; \
		exit 1; \
	fi
	@if ! command -v pnpm >/dev/null 2>&1; then \
		echo "[INFO] Installing pnpm via corepack..."; \
		corepack enable && corepack prepare pnpm@latest --activate; \
	fi
	@echo "[INFO] Installing wizard dependencies..."
	@cd "$(WIZARD_DIR)" && pnpm install
	@cd "$(WIZARD_DIR)" && pnpm --filter @sd-creation-wizard/shacl-core build
	@echo "[OK] Wizard setup complete. Run 'make wizard' to start."
else
	@if [ -f .gitmodules ]; then \
		if ! command -v $(GIT) >/dev/null 2>&1; then \
			echo "[WARN] Git is not available -- skipping submodule initialization."; \
		elif $(GIT) rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
			echo "[INFO] Initializing git submodules..."; \
			$(GIT) submodule update --init; \
		else \
			echo "[WARN] .gitmodules found, but this checkout is not a git worktree -- skipping submodule initialization."; \
		fi; \
	fi
	@"$(MAKE)" --no-print-directory $(ACTIVATE_SCRIPT)
	@if ! "$(PYTHON)" -c "import rdflib, pyshacl, lxml" >/dev/null 2>&1; then \
		echo "[INFO] Dependencies missing -- reinstalling..."; \
		"$(PYTHON)" -m pip install -e ".[dev]"; \
	fi
	@echo "[INFO] Installing quality checker tools..."
	@git config --global core.longpaths true 2>/dev/null || true
	@"$(PYTHON)" -m pip install -e ".[qc,qc-deps]"
	@if [ -f "$(OMB)/pyproject.toml" ] || [ -f "$(OMB)/setup.py" ]; then \
		echo "[INFO] Installing ontology-management-base..."; \
		"$(PYTHON)" -m pip install -e "$(OMB)"; \
	else \
		echo "[WARN] OMB submodule not initialised – skipping."; \
	fi
	@"$(PYTHON)" -m pre_commit install --allow-missing-config >/dev/null 2>&1 || true
	@if command -v node >/dev/null 2>&1; then \
		echo "[INFO] Setting up wizard (Node.js found)..."; \
		if ! command -v pnpm >/dev/null 2>&1; then \
			echo "[INFO] Installing pnpm via corepack..."; \
			corepack enable && corepack prepare pnpm@latest --activate; \
		fi; \
		cd "$(WIZARD_DIR)" && pnpm install && pnpm --filter @sd-creation-wizard/shacl-core build; \
		echo "[OK] Wizard ready. Run 'make wizard' to start."; \
	else \
		echo "[INFO] Node.js not found -- skipping wizard setup (optional)."; \
		echo "       Install Node.js 22+ and run 'make setup wizard' to enable the wizard."; \
	fi
	@echo "[OK] Setup complete. Activate with: $(ACTIVATE_HINT)"
endif

$(PYTHON):
	@echo "[INFO] Creating virtual environment at $(VENV)..."
	@"$(BOOTSTRAP_PYTHON)" -m venv "$(VENV)"
	@"$(PYTHON)" -m pip install --upgrade pip

$(ACTIVATE_SCRIPT): $(PYTHON)
	@echo "[INFO] Installing dependencies..."
	@"$(PYTHON)" -m pip install -e ".[dev]"
	@touch "$(ACTIVATE_SCRIPT)"

install:
	$(call check_dev_setup)
	@git config --global core.longpaths true 2>/dev/null || true
	@"$(PYTHON)" -m pip install -e ".[dev,qc,qc-deps]"
	@if [ -f "$(OMB)/pyproject.toml" ] || [ -f "$(OMB)/setup.py" ]; then \
		"$(PYTHON)" -m pip install -e "$(OMB)"; \
	else \
		echo "[WARN] OMB submodule not initialised – skipping."; \
	fi
	@echo "[OK] Install complete"

# ── Lint & Format ────────────────────────────────────────────────────

lint:
	$(call check_dev_setup)
	@echo "[INFO] Linting..."
	@"$(PYTHON)" -m ruff check $(PY_FILES)
	@"$(PYTHON)" -m ruff format --check $(PY_FILES)
	@echo "[OK] Lint passed"

lint-md:
	@echo "[INFO] Linting Markdown..."
	@npx --yes markdownlint-cli2 "README.md" "**/README.md" "!submodules/**" "!.venv/**" "!.pytest_cache/**"
	@echo "[OK] Markdown lint passed"

# Guard: skip when `format` is a subcommand argument (e.g. make check format)
format:
ifneq ($(firstword $(MAKECMDGOALS)),format)
	@:
else
	$(call check_dev_setup)
	@echo "[INFO] Formatting..."
	@"$(PYTHON)" -m ruff check --fix $(PY_FILES)
	@"$(PYTHON)" -m ruff format $(PY_FILES)
	@echo "[OK] Format complete"
endif

format-md:
	@echo "[INFO] Formatting Markdown..."
	@npx --yes markdownlint-cli2 --fix "README.md" "**/README.md" "!submodules/**" "!.venv/**" "!.pytest_cache/**"
	@echo "[OK] Markdown format complete"

# ── Check (with subcommands) ─────────────────────────────────────────

check:
	$(call check_dev_setup)
ifeq ($(SUBCMD),format)
	@echo "[INFO] Checking formatting..."
	@"$(PYTHON)" -m ruff format --check $(PY_FILES)
else ifeq ($(SUBCMD),py)
	@echo "[INFO] Compile-checking Python files..."
	@"$(PYTHON)" scripts/check_py_compile.py
else ifeq ($(SUBCMD),readme)
	@echo "[INFO] Validating README structure..."
	@"$(PYTHON)" scripts/check_readme_style.py
else ifeq ($(SUBCMD),md)
	@echo "[INFO] Linting Markdown..."
	@npx --yes markdownlint-cli2 "README.md" "**/README.md" "!submodules/**" "!.venv/**" "!.pytest_cache/**"
else
	@echo "[INFO] Running all checks..."
	@"$(PYTHON)" -m ruff format --check $(PY_FILES)
	@"$(PYTHON)" scripts/check_py_compile.py
	@"$(PYTHON)" scripts/check_readme_style.py
	@npx --yes markdownlint-cli2 "README.md" "**/README.md" "!submodules/**" "!.venv/**" "!.pytest_cache/**"
endif
	@echo "[OK] Check passed"

# ── Validate ─────────────────────────────────────────────────────────

validate:
	$(call check_dev_setup)
	@json_files=$$(find examples/assets -name 'manifest.json' -o -name '*.json' -path '*/metadata/*' 2>/dev/null); \
	if [ -z "$$json_files" ]; then \
		echo "[SKIP] No generated assets found. Run:  make generate opendrive"; \
		exit 0; \
	fi; \
	echo "[INFO] Running SHACL conformance validation..."; \
	echo "[INFO] Files: $$json_files"; \
	"$(PYTHON)" -m src.tools.validators.validation_suite \
		--run check-data-conformance \
		--data-paths $$json_files \
		--artifacts "$(OMB)/artifacts"; \
	echo "[OK] Validation complete"

# ── Generate pipeline ─────────────────────────────────────────────────

# All pipeline output goes to examples/assets/ by default.
ASSETS_DIR := $(CURDIR)/examples/assets
OUTPUT_DIR ?= $(ASSETS_DIR)

generate:
	$(call check_dev_setup)
ifneq ($(INPUT_DIR),)
	@if [ ! -f "$(INPUT_DIR)/input_manifest.json" ]; then \
		echo "[ERR] No input_manifest.json found in $(INPUT_DIR)"; \
		exit 1; \
	fi
	@mkdir -p "$(OUTPUT_DIR)" 2>/dev/null || true
	@echo "[INFO] Running pipeline from $(INPUT_DIR)..."
	@"$(PYTHON)" -m asset_extraction.main \
		"$(INPUT_DIR)/input_manifest.json" \
		-config "$(CURDIR)/configs" \
		-out "$(OUTPUT_DIR)" \
		$(if $(ZIP_DIR),-zip-dir "$(ZIP_DIR)") \
		$(PIPELINE_FLAGS)
	@echo "[OK] Pipeline complete -> $(OUTPUT_DIR)"
else ifeq ($(SUBCMD),batch)
	@echo "[INFO] Batch-processing all input manifests under examples/..."
	@mkdir -p "$(OUTPUT_DIR)" 2>/dev/null || true
	@rm -f "$(OUTPUT_DIR)/.asset_registry.json"
	@"$(PYTHON)" -m batch_runner batch \
		"$(CURDIR)/examples" \
		-config "$(CURDIR)/configs" \
		-out "$(OUTPUT_DIR)" \
		-zip-dir "$(ASSETS_DIR)" \
		$(PIPELINE_FLAGS)
	@echo "[OK] Batch complete -> $(OUTPUT_DIR)"
else
	@dir="$(EXAMPLE_$(SUBCMD))"; \
	if [ -z "$$dir" ]; then \
		echo "[ERR] Unknown example: $(SUBCMD)"; \
		echo "Usage:  make $@ <opendrive|openscenario|batch>"; \
		echo "        make $@ INPUT_DIR=path/to/input OUTPUT_DIR=path/to/output"; \
		exit 1; \
	fi; \
	status=0; \
	if [ "$(SUBCMD)" = "openscenario" ]; then \
		if [ ! -f "$(ASSETS_DIR)/.asset_registry.json" ]; then \
			echo "[INFO] OpenScenario references an OpenDRIVE map -- building dependency first..."; \
			"$(MAKE)" generate opendrive || status=$$?; \
		fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		echo "[INFO] Running $$dir pipeline..."; \
		"$(PYTHON)" -m asset_extraction.main \
			"$(CURDIR)/examples/$$dir/input_manifest.json" \
			-config "$(CURDIR)/configs" \
			-out   "$(ASSETS_DIR)" \
			-zip-dir "$(ASSETS_DIR)" \
			$(PIPELINE_FLAGS) || status=$$?; \
	fi; \
	if [ $$status -ne 0 ]; then \
		echo "[ERR] $$dir pipeline failed (exit $$status)"; \
		exit $$status; \
	fi; \
	echo "[OK] $$dir pipeline complete"
endif

# ── Review (interactive metadata review) ─────────────────────────────

REVIEW_DIR ?= $(ASSETS_DIR)

review:
	$(call check_dev_setup)
	@echo "[INFO] Reviewing assets under $(REVIEW_DIR)..."
	@WIZARD_ENABLED=true "$(PYTHON)" -m batch_runner review \
		"$(REVIEW_DIR)" \
		-config "$(CURDIR)/configs" \
		-zip-dir "$(REVIEW_DIR)"
	@echo "[OK] Review complete"

# ── Wizard (SD Creation Wizard API) ──────────────────────────────────

wizard:
ifeq ($(SUBCMD),stop)
	@if [ -f /tmp/sd-wizard-api.pid ]; then \
		pid=$$(cat /tmp/sd-wizard-api.pid); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -- -$$pid 2>/dev/null || kill $$pid; \
			echo "[OK] Wizard API stopped (PID $$pid)"; \
		else \
			echo "[INFO] Wizard API was not running"; \
		fi; \
		rm -f /tmp/sd-wizard-api.pid; \
	else \
		echo "[INFO] No PID file found — wizard may not be running"; \
	fi
else
	@if ! command -v node >/dev/null 2>&1; then \
		echo "[ERR] Node.js is required. Install it first."; \
		exit 1; \
	fi
	@if ! command -v pnpm >/dev/null 2>&1; then \
		echo "[INFO] Installing pnpm via corepack..."; \
		corepack enable && corepack prepare pnpm@latest --activate; \
	fi
	@if [ ! -d "$(WIZARD_DIR)/node_modules" ]; then \
		echo "[INFO] Installing wizard dependencies..."; \
		cd "$(WIZARD_DIR)" && pnpm install; \
	fi
	@if [ ! -d "$(WIZARD_DIR)/packages/shacl-core/dist" ]; then \
		echo "[INFO] Building shacl-core..."; \
		cd "$(WIZARD_DIR)" && pnpm --filter @sd-creation-wizard/shacl-core build; \
	fi
	@echo "[INFO] Starting SD Creation Wizard API..."
	@cd "$(WIZARD_DIR)/apps/api" && setsid nohup npx tsx src/index.ts > /tmp/sd-wizard-api.log 2>&1 & echo $$! > /tmp/sd-wizard-api.pid
	@sleep 2
	@if kill -0 $$(cat /tmp/sd-wizard-api.pid) 2>/dev/null; then \
		echo ""; \
		echo "[OK] Wizard API is running:"; \
		echo "  API:      http://localhost:$(WIZARD_API_PORT)"; \
		echo "  Frontend: http://localhost:$(WIZARD_FRONTEND_PORT)"; \
		echo ""; \
		echo "  Stop with:  make wizard stop"; \
	else \
		echo "[ERR] Wizard API failed to start. Check errors above."; \
		rm -f /tmp/sd-wizard-api.pid; \
		exit 1; \
	fi
endif

# ── Clean ────────────────────────────────────────────────────────────

clean:
ifeq ($(SUBCMD),all)
	@echo "[INFO] Cleaning everything..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@rm -rf examples/assets
	@rm -rf "$(VENV)"
	@if [ -f .gitmodules ] && $(GIT) rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		$(GIT) submodule deinit --all --force 2>/dev/null || true; \
	fi
	@echo "[OK] Full clean complete -- run 'make setup' to reinitialise"
else
	@echo "[INFO] Cleaning..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@rm -rf examples/assets
	@echo "[OK] Cleaned"
endif

# ── Help ─────────────────────────────────────────────────────────────

help:
	@echo "sl-5-8-asset-tools -- Available Commands"
	@echo ""
	@echo "  make setup                   Create venv, init submodules, install deps + wizard"
	@echo "  make install                 Reinstall all dependencies (dev, QC, OMB)"
	@echo ""
	@echo "  make lint                    Lint checks (ruff)"
	@echo "  make lint-md                 Lint Markdown files"
	@echo "  make format                  Auto-format code (ruff)"
	@echo "  make format-md               Auto-fix Markdown lint issues"
	@echo ""
	@echo "  make check                   Run all checks (format, compile, readme, markdown)"
	@echo "  make check format            Check formatting only"
	@echo "  make check py                Compile-check all Python files"
	@echo "  make check readme            Validate README structure"
	@echo "  make check md                Lint Markdown files"
	@echo ""
	@echo "  make validate                Validate generated examples against SHACL"
	@echo ""
	@echo "  make generate opendrive      Run OpenDRIVE example pipeline"
	@echo "  make generate openscenario   Run OpenSCENARIO example pipeline"
	@echo "  make generate batch          Batch-process all examples (hdmap first, then scenario)"
	@echo "  make generate INPUT_DIR=<path> OUTPUT_DIR=<path>"
	@echo "                               Run pipeline for a custom input directory"
	@echo ""
	@echo "Interactive wizard (opens browser for metadata enrichment):"
	@echo "  WIZARD=true make generate opendrive"
	@echo "  WIZARD=true make generate INPUT_DIR=<path> OUTPUT_DIR=<path>"
	@echo "                               Pauses pipeline at wizard step, opens browser"
	@echo "                               with pre-filled form, waits for user export."
	@echo ""
	@echo "Pipeline module flags (pass via PIPELINE_FLAGS):"
	@echo "  PIPELINE_FLAGS='-disable vcs_odr-converter' make generate opendrive"
	@echo "                               Skip specific modules (blacklist)"
	@echo "  PIPELINE_FLAGS='-enable meta_data_extractor structure_creator' make generate opendrive"
	@echo "                               Run only specified modules (whitelist)"
	@echo "  PIPELINE_FLAGS='-list-modules' make generate opendrive"
	@echo "                               List available module IDs and exit"
	@echo ""
	@echo "  Note: xodr_to_geojson_caller (vcs_odr-converter) is disabled by default."
	@echo "        Enable with: PIPELINE_FLAGS='-enable vcs_odr-converter'"
	@echo ""
	@echo "  make wizard                  Start SD Creation Wizard API (Node.js)"
	@echo "  make wizard stop             Stop the wizard API"
	@echo "  make setup wizard            Reinstall wizard dependencies only"
	@echo ""
	@echo "Metadata review (interactive — enriches, reviews, and re-zips):"
	@echo "  make review                  Review all assets in examples/assets/ via wizard"
	@echo "  make review REVIEW_DIR=<path>"
	@echo "                               Review assets in a custom directory"
	@echo ""
	@echo "  validate = automated SHACL conformance check (read-only, pass/fail)"
	@echo "  review   = interactive human review via wizard (may enrich and re-zip)"
	@echo ""
	@echo "  make clean                   Remove build artifacts and caches"
	@echo "  make clean all               Clean + remove venv and submodules (full reset)"
	@echo ""
	@echo "Debug logging:"
	@echo "  SL58_LOG_MODE=debug make generate opendrive"
	@echo "  Shows full subprocess command lines, stdout/stderr, and tracebacks."
	@echo ""
	@echo "Deterministic mode (reproducible output):"
	@echo "  SL58_DETERMINISTIC=1 make generate opendrive"
	@echo "  Same input files produce identical UUIDs, timestamps, and CID."

# ── Catch-all for subcommand arguments ───────────────────────────────
# Prevents "No rule to make target 'opendrive'" errors
ifneq ($(filter setup generate check wizard clean review,$(firstword $(MAKECMDGOALS))),)
%:
	@:
endif
