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
# Enables:  make run opendrive,  make check format,  make install dev
SUBCMD = $(word 2,$(MAKECMDGOALS))

# Example directory mapping for `make run <example>`
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

.PHONY: all setup install lint format check validate generate clean help init-submodules

# Default target
all: check

# ── Setup & Install ──────────────────────────────────────────────────

init-submodules:
	@if [ -f .gitmodules ]; then \
		if ! command -v $(GIT) >/dev/null 2>&1; then \
			echo "[WARN] Git is not available -- skipping submodule initialization."; \
		elif $(GIT) rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
			echo "[INFO] Initializing git submodules..."; \
			$(GIT) submodule update --init --recursive; \
		else \
			echo "[WARN] .gitmodules found, but this checkout is not a git worktree -- skipping submodule initialization."; \
		fi; \
	fi

setup:
	@$(MAKE) --no-print-directory init-submodules
	@$(MAKE) --no-print-directory $(ACTIVATE_SCRIPT)
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
else
	@echo "[INFO] Running all checks..."
	@"$(PYTHON)" -m ruff format --check $(PY_FILES)
	@"$(PYTHON)" scripts/check_py_compile.py
	@"$(PYTHON)" scripts/check_readme_style.py
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
	@dir="$(EXAMPLE_$(SUBCMD))"; \
	if [ -z "$$dir" ]; then \
		echo "[ERR] Unknown example: $(SUBCMD)"; \
		echo "Usage:  make $@ <opendrive|openscenario>"; \
		exit 1; \
	fi; \
	bak="$(CURDIR)/examples/$$dir/input/input_manifest.json.bak"; \
	status=0; \
	restore_status=0; \
	if [ "$(SUBCMD)" = "openscenario" ]; then \
		odr_manifest=$$(find "$(CURDIR)/examples/OpenDRIVE/output" -name manifest.json 2>/dev/null | head -1); \
		if [ -z "$$odr_manifest" ]; then \
			echo "[INFO] OpenDRIVE asset not built yet — building dependency..."; \
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
		cd "./examples/$$dir/input" && "$(CURDIR)/$(PYTHON)" -m asset_extraction.main \
			input_manifest.json \
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

# ── Clean ────────────────────────────────────────────────────────────

clean:
	@echo "[INFO] Cleaning..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf examples/OpenDRIVE/output examples/OpenSCENARIO/output
	@rm -f examples/OpenDRIVE/*.zip examples/OpenSCENARIO/*.zip
	@echo "[OK] Cleaned"

# ── Help ─────────────────────────────────────────────────────────────

help:
	@echo "sl-5-8-asset-tools -- Available Commands"
	@echo ""
	@echo "  make setup                   Create venv, init submodules, and install dependencies"
	@echo "  make install                 Install package"
	@echo "  make install dev             Install with dev dependencies"
	@echo ""
	@echo "  make lint                    Lint checks (ruff)"
	@echo "  make format                  Auto-format code (ruff)"
	@echo ""
	@echo "  make check                   Run all checks (format, compile, readme)"
	@echo "  make check format            Check formatting only"
	@echo "  make check py                Compile-check all Python files"
	@echo "  make check readme            Validate README structure"
	@echo ""
	@echo "  make validate                Validate generated examples against SHACL"
	@echo ""
	@echo "  make generate opendrive      Run OpenDRIVE example pipeline"
	@echo "  make generate openscenario   Run OpenSCENARIO example pipeline"
	@echo ""
	@echo "  make clean                   Remove build artifacts and caches"
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
ifneq ($(filter generate check install,$(firstword $(MAKECMDGOALS))),)
%:
	@:
endif
