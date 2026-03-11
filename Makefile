# Makefile for sl-5-8-asset-tools
# Build command center for common development tasks

# Allow parent makefiles to override the venv path/tooling.
VENV ?= .venv
OMB  := submodules/ontology-management-base

# OS detection for cross-platform support (Windows vs Unix)
ifeq ($(OS),Windows_NT)
    VENV_BIN         := $(VENV)/Scripts
    PYTHON           ?= $(VENV_BIN)/python.exe
    BOOTSTRAP_PYTHON ?= python
else
    VENV_BIN         := $(VENV)/bin
    PYTHON           ?= $(VENV_BIN)/python3
    BOOTSTRAP_PYTHON ?= python3
endif
ACTIVATE_SCRIPT := $(VENV_BIN)/activate

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

.PHONY: all setup install lint format check validate run clean help

# Default target
all: check

# ── Setup & Install ──────────────────────────────────────────────────

setup: $(ACTIVATE_SCRIPT)
	@if ! "$(PYTHON)" -c "import rdflib, pyshacl, lxml" >/dev/null 2>&1; then \
		echo "[INFO] Dependencies missing -- reinstalling..."; \
		"$(PYTHON)" -m pip install -e ".[dev]"; \
		"$(PYTHON)" -m pip install -e "$(OMB)"; \
	fi
	@"$(PYTHON)" -m pre_commit install --allow-missing-config >/dev/null 2>&1 || true
	@echo "[OK] Setup complete.  Activate with:  source $(ACTIVATE_SCRIPT)"

$(PYTHON):
	@echo "[INFO] Creating virtual environment at $(VENV)..."
	@"$(BOOTSTRAP_PYTHON)" -m venv "$(VENV)"
	@"$(PYTHON)" -m pip install --upgrade pip

$(ACTIVATE_SCRIPT): $(PYTHON)
	@echo "[INFO] Installing dependencies..."
	@"$(PYTHON)" -m pip install -e ".[dev]"
	@"$(PYTHON)" -m pip install -e "$(OMB)"
	@touch "$(ACTIVATE_SCRIPT)"

install:
	$(call check_dev_setup)
ifeq ($(SUBCMD),dev)
	@"$(PYTHON)" -m pip install -e ".[dev]"
else
	@"$(PYTHON)" -m pip install -e .
endif
	@"$(PYTHON)" -m pip install -e "$(OMB)"
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
	@echo "[INFO] Running SHACL conformance validation..."
	@"$(PYTHON)" -m src.tools.validators.validation_suite \
		--run check-data-conformance \
		--artifacts "$(OMB)/artifacts"
	@echo "[OK] Validation complete"

# ── Run pipeline ─────────────────────────────────────────────────────

run:
	$(call check_dev_setup)
	@dir="$(EXAMPLE_$(SUBCMD))"; \
	if [ -z "$$dir" ]; then \
		echo "[ERR] Unknown example: $(SUBCMD)"; \
		echo "Usage:  make run <opendrive|openscenario>"; \
		exit 1; \
	fi; \
	echo "[INFO] Running $$dir pipeline..."; \
	"$(PYTHON)" -m asset_extraction.main \
		"./examples/$$dir/uploadedFiles.json" \
		-config "./configs" \
		-out   "./examples/$$dir/output"; \
	echo "[OK] $$dir pipeline complete"

# ── Clean ────────────────────────────────────────────────────────────

clean:
	@echo "[INFO] Cleaning..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf examples/OpenDRIVE/output examples/OpenSCENARIO/output
	@echo "[OK] Cleaned"

# ── Help ─────────────────────────────────────────────────────────────

help:
	@echo "sl-5-8-asset-tools -- Available Commands"
	@echo ""
	@echo "  make setup              Create venv and install all dependencies"
	@echo "  make install            Install package"
	@echo "  make install dev        Install with dev dependencies"
	@echo ""
	@echo "  make lint               Lint checks (ruff)"
	@echo "  make format             Auto-format code (ruff)"
	@echo ""
	@echo "  make check              Run all checks (format, compile, readme)"
	@echo "  make check format       Check formatting only"
	@echo "  make check py           Compile-check all Python files"
	@echo "  make check readme       Validate README structure"
	@echo ""
	@echo "  make validate           SHACL data conformance validation"
	@echo ""
	@echo "  make run opendrive      Run OpenDRIVE example pipeline"
	@echo "  make run openscenario   Run OpenSCENARIO example pipeline"
	@echo ""
	@echo "  make clean              Remove build artifacts and caches"

# ── Catch-all for subcommand arguments ───────────────────────────────
# Prevents "No rule to make target 'opendrive'" errors
ifneq ($(filter run check install,$(firstword $(MAKECMDGOALS))),)
%:
	@:
endif
