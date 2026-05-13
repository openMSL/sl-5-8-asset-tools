# Setup

## Prerequisites

- Python 3.12+
- Git (for submodule initialization)
- Node.js 20+ (optional, for the SD Creation Wizard)

## Install

```bash
git clone https://github.com/openMSL/sl-5-8-asset-tools.git
cd sl-5-8-asset-tools
make setup
```

All dependencies are managed via `pyproject.toml` and installed automatically
by `make setup`. Git submodules are initialized automatically when running
from a git checkout.

On Windows, run `make` from Git Bash or another POSIX `sh`-compatible shell.

## Wizard Setup (Optional)

If Node.js is available, `make setup` also installs the
[SD Creation Wizard](https://github.com/2getthere/sd-creation-wizard)
for interactive metadata enrichment. To install wizard dependencies
separately:

```bash
make setup wizard
```

## Available Commands

Run `make help` for the full list:

```bash
make help
```

Key commands:

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, init submodules, install deps |
| `make install` | Reinstall all dependencies |
| `make lint` | Lint checks (ruff) |
| `make format` | Auto-format code |
| `make check` | Run all checks (format, compile, readme, markdown) |
| `make validate` | Validate generated assets against SHACL |
| `make generate <example>` | Run a pipeline example |
| `make init INPUT_DIR=<path>` | Generate input manifest from files |
| `make wizard` | Start the SD Creation Wizard |
| `make review` | Interactive metadata review |
| `make clean` | Remove build artifacts |
