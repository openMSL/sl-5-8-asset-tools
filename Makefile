# Makefile for sl-5-8-asset-tools
# Build command center for common development tasks

# Allow parent makefiles to override the venv path/tooling.
VENV ?= .venv
OMB  := submodules/ontology-management-base
GIT  ?= git

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
# Enables:  make generate opendrive,  make check format,  make install dev
SUBCMD = $(word 2,$(MAKECMDGOALS))

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
	@if command -v podman >/dev/null 2>&1; then \
		echo "[OK] Podman is already installed."; \
	elif [ "$(OS)" = "Windows_NT" ]; then \
		echo "[INFO] Installing Podman Desktop via winget..."; \
		winget install --id RedHat.Podman-Desktop --source winget --accept-source-agreements --accept-package-agreements; \
		winget install --id RedHat.Podman --source winget --accept-source-agreements --accept-package-agreements; \
		echo ""; \
		echo "[OK] Podman installed."; \
		echo ""; \
		echo "  Next steps (one-time, requires an admin terminal):"; \
		echo "    wsl --install --no-distribution   (reboot required)"; \
		echo "    podman machine init"; \
		echo "    podman machine start"; \
		echo ""; \
		echo "  Or open Podman Desktop from the Start menu -- it will guide you through setup."; \
		echo "  Then restart your shell and run 'make wizard'."; \
	else \
		echo "[INFO] Installing Podman via apt..."; \
		sudo apt-get update -qq && sudo apt-get install -y -qq podman podman-compose; \
		echo "[OK] Podman installed. Run 'make wizard' to start."; \
	fi
	@if [ "$(OS)" = "Windows_NT" ] && command -v podman >/dev/null 2>&1; then \
		if ! command -v podman-compose >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then \
			echo "[INFO] Installing podman-compose..."; \
			"$(PYTHON)" -m pip install podman-compose --quiet 2>/dev/null \
				|| pip install podman-compose --quiet; \
			echo "[OK] podman-compose installed."; \
		fi; \
	fi
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
	@if [ -f "$(OMB)/pyproject.toml" ] || [ -f "$(OMB)/setup.py" ]; then \
		echo "[INFO] Installing ontology-management-base..."; \
		"$(PYTHON)" -m pip install -e "$(OMB)"; \
	else \
		echo "[WARN] OMB submodule not initialised – skipping."; \
	fi
	@"$(PYTHON)" -m pre_commit install --allow-missing-config >/dev/null 2>&1 || true
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
ifeq ($(SUBCMD),dev)
	@"$(PYTHON)" -m pip install -e ".[dev]"
else ifeq ($(SUBCMD),qc)
	@git config --global core.longpaths true 2>/dev/null || true
	@"$(PYTHON)" -m pip install -e ".[qc,qc-deps]"
else
	@"$(PYTHON)" -m pip install -e .
endif
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
	@json_files=$$(find examples/*/output -name 'manifest.json' -o -name '*.json' -path '*/metadata/*' 2>/dev/null); \
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
		$(if $(ZIP_DIR),-zip-dir "$(ZIP_DIR)")
	@echo "[OK] Pipeline complete -> $(OUTPUT_DIR)"
else
	@dir="$(EXAMPLE_$(SUBCMD))"; \
	if [ -z "$$dir" ]; then \
		echo "[ERR] Unknown example: $(SUBCMD)"; \
		echo "Usage:  make $@ <opendrive|openscenario>"; \
		echo "        make $@ INPUT_DIR=path/to/input OUTPUT_DIR=path/to/output"; \
		exit 1; \
	fi; \
	bak="$(CURDIR)/examples/$$dir/input/input_manifest.json.bak"; \
	status=0; \
	restore_status=0; \
	if [ "$(SUBCMD)" = "openscenario" ]; then \
		odr_manifest=$$(find "$(CURDIR)/examples/OpenDRIVE/output" -name manifest.json 2>/dev/null | head -1); \
		if [ -z "$$odr_manifest" ]; then \
			echo "[INFO] OpenScenario references an OpenDRIVE map -- building dependency first..."; \
			"$(MAKE)" generate opendrive || status=$$?; \
			if [ $$status -eq 0 ]; then \
				odr_manifest=$$(find "$(CURDIR)/examples/OpenDRIVE/output" -name manifest.json 2>/dev/null | head -1); \
			fi; \
		fi; \
		if [ $$status -eq 0 ] && [ -n "$$odr_manifest" ]; then \
			echo "[INFO] Resolving external references from $$odr_manifest"; \
			cp "$(CURDIR)/examples/$$dir/input/input_manifest.json" \
			   "$$bak" || status=$$?; \
			if [ $$status -eq 0 ]; then \
				"$(CURDIR)/$(PYTHON)" "$(CURDIR)/scripts/resolve_references.py" \
					"$(CURDIR)/examples/$$dir/input/input_manifest.json" \
					--ref-manifest "$$odr_manifest" || status=$$?; \
			fi; \
		fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		echo "[INFO] Running $$dir pipeline..."; \
		"$(PYTHON)" -m asset_extraction.main \
			"$(CURDIR)/examples/$$dir/input/input_manifest.json" \
			-config "$(CURDIR)/configs" \
			-out   "$(CURDIR)/examples/$$dir/output" \
			-zip-dir "$(CURDIR)/examples/$$dir" || status=$$?; \
	fi; \
	if [ -f "$$bak" ]; then \
		mv "$$bak" "$(CURDIR)/examples/$$dir/input/input_manifest.json" || restore_status=$$?; \
	fi; \
	if [ $$restore_status -ne 0 ]; then \
		echo "[ERR] Failed to restore input manifest"; \
		if [ $$status -eq 0 ]; then \
			status=$$restore_status; \
		fi; \
	fi; \
	if [ $$status -ne 0 ]; then \
		echo "[ERR] $$dir pipeline failed (exit $$status)"; \
		exit $$status; \
	fi; \
	echo "[OK] $$dir pipeline complete"
endif

# ── Wizard (SD Creation Wizard frontend + API) ───────────────────────

COMPOSE_WIZARD := podman compose -f docker-compose.wizard.yml -p sl58-wizard

# Optional: mount corporate Maven / npm config into container builds.
#   make wizard MAVEN_SETTINGS=~/.m2 NPM_CONFIG=~/.npmrc
# When either is set, images are built individually with --volume flags
# before starting compose (podman-compose does not support build volumes).
MAVEN_SETTINGS ?=
NPM_CONFIG     ?=

wizard:
ifeq ($(SUBCMD),stop)
	@$(COMPOSE_WIZARD) down
	@echo "[OK] Wizard stopped"
else
	@if ! command -v podman >/dev/null 2>&1; then \
		"$(MAKE)" --no-print-directory setup wizard; \
		echo ""; \
		echo "[INFO] Restart your shell and start Podman Desktop, then run 'make wizard' again."; \
		exit 0; \
	fi
	@if [ "$(OS)" = "Windows_NT" ]; then \
		if ! podman machine inspect >/dev/null 2>&1; then \
			echo "[INFO] No Podman machine found. Initialising..."; \
			podman machine init; \
		fi; \
		if [ "$$(podman machine inspect --format '{{.State}}' 2>/dev/null)" != "running" ]; then \
			echo "[INFO] Starting Podman machine..."; \
			podman machine start; \
		fi; \
	fi
	@if ! command -v podman-compose >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then \
		echo "[INFO] No compose provider found. Installing podman-compose..."; \
		"$(PYTHON)" -m pip install podman-compose --quiet 2>/dev/null \
			|| pip install podman-compose --quiet; \
	fi
	@"$(PYTHON)" -c "\
	import importlib, re, pathlib; \
	mod = importlib.import_module('podman_compose'); \
	p = pathlib.Path(mod.__file__); src = p.read_text(); \
	bad = 'dockerfile = os.path.normpath(os.path.join(ctx, dockerfile))'; \
	fix = 'dockerfile = os.path.normpath(dockerfile)'; \
	p.write_text(src.replace(bad, fix)) if bad in src else None; \
	" 2>/dev/null || true
	@echo "[INFO] Building and starting SD Creation Wizard..."
	@vol_args=""; \
	if [ -n "$(MAVEN_SETTINGS)" ]; then \
		_p=$$(eval echo "$(MAVEN_SETTINGS)"); \
		vol_args="$$vol_args --volume $$_p:/root/.m2:z"; \
	fi; \
	if [ -n "$(NPM_CONFIG)" ]; then \
		_p=$$(eval echo "$(NPM_CONFIG)"); \
		vol_args="$$vol_args --volume $$_p:/root/.npmrc:z"; \
	fi; \
	build_ok=true; \
	if [ -n "$$vol_args" ]; then \
		echo "[INFO] Custom build volumes:$$vol_args"; \
		podman build $$vol_args \
			-f submodules/sd-creation-wizard-api/deployment/docker/Dockerfile \
			-t sd-creation-wizard-api:local \
			submodules/sd-creation-wizard-api || build_ok=false; \
		if $$build_ok; then \
			podman build $$vol_args \
				-f submodules/sd-creation-wizard-frontend/deployment/docker/Dockerfile \
				-t sd-creation-wizard:local \
				submodules/sd-creation-wizard-frontend || build_ok=false; \
		fi; \
	fi; \
	if ! $$build_ok; then \
		echo ""; \
		echo "[ERR] Image build failed. Check the errors above."; \
		exit 1; \
	fi; \
	compose_build=""; \
	if [ -z "$$vol_args" ]; then compose_build="--build"; fi; \
	if $(COMPOSE_WIZARD) up $$compose_build -d; then \
		echo ""; \
		echo "[OK] Wizard is running:"; \
		echo "  Frontend: http://localhost:4200"; \
		echo "  API:      http://localhost:8080"; \
		echo ""; \
		echo "  Stop with:  make wizard stop"; \
	else \
		echo ""; \
		echo "[ERR] Failed to start the wizard. Check the errors above."; \
		echo ""; \
		echo "  Common causes:"; \
		echo "    - Podman machine not running  →  podman machine start"; \
		echo "    - Corporate proxy             →  see README \"Corporate Network\" section"; \
		echo "    - Port already in use          →  make wizard stop, then retry"; \
		exit 1; \
	fi
endif

# ── Clean ────────────────────────────────────────────────────────────

clean:
ifeq ($(SUBCMD),all)
	@echo "[INFO] Cleaning everything..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@rm -rf examples/OpenDRIVE/output examples/OpenSCENARIO/output
	@rm -f examples/OpenDRIVE/*.zip examples/OpenSCENARIO/*.zip
	@rm -rf "$(VENV)"
	@if [ -f .gitmodules ] && $(GIT) rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		$(GIT) submodule deinit --all --force 2>/dev/null || true; \
	fi
	@echo "[OK] Full clean complete -- run 'make setup' to reinitialise"
else
	@echo "[INFO] Cleaning..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@rm -rf examples/OpenDRIVE/output examples/OpenSCENARIO/output
	@rm -f examples/OpenDRIVE/*.zip examples/OpenSCENARIO/*.zip
	@echo "[OK] Cleaned"
endif

# ── Help ─────────────────────────────────────────────────────────────

help:
	@echo "sl-5-8-asset-tools -- Available Commands"
	@echo ""
	@echo "  make setup                   Create venv, init submodules, and install dependencies"
	@echo "  make install                 Install package"
	@echo "  make install dev             Install with dev dependencies"
	@echo "  make install qc              Install quality checker tools (ASAM, OpenMSL)"
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
	@echo "  make generate INPUT_DIR=<path> OUTPUT_DIR=<path>"
	@echo "                               Run pipeline for a custom input directory"
	@echo ""
	@echo "  make wizard                  Start SD Creation Wizard (Podman, auto-setup if needed)"
	@echo "  make wizard stop             Stop the wizard containers"
	@echo "  make setup wizard            Install Podman + compose provider (called by wizard)"
	@echo "  make wizard MAVEN_SETTINGS=~/.m2 NPM_CONFIG=~/.npmrc"
	@echo "                               Build with custom Maven/npm config (corporate mirrors)"
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
ifneq ($(filter setup generate check install wizard clean,$(firstword $(MAKECMDGOALS))),)
%:
	@:
endif
