PYTHON ?= python
BLACK ?= $(PYTHON) -m black
PY_FILES := $(shell git ls-files '*.py')

.PHONY: help format check check-format check-py check-readme

help:
	@echo "Targets:"
	@echo "  make format        Format all tracked Python files with black"
	@echo "  make check         Run all repository checks"
	@echo "  make check-format  Check Python formatting with black --check"
	@echo "  make check-py      Compile all tracked Python files"
	@echo "  make check-readme  Validate README section structure"

format:
	$(BLACK) $(PY_FILES)

check: check-format check-py check-readme

check-format:
	$(BLACK) --check $(PY_FILES)

check-py:
	@$(PYTHON) scripts/check_py_compile.py

check-readme:
	@$(PYTHON) scripts/check_readme_style.py
