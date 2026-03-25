# Documentation And Style Guide

This guide defines formatting and documentation standards for this repository.

## Python Formatting

- Use Python 3.12.
- Use `ruff` as the canonical formatter and linter.
- Format all tracked Python files before commit:

```bash
make format
```

- Quick syntax verification:

```bash
python - <<'PY'
import subprocess, py_compile
files = subprocess.check_output(['git', 'ls-files', '*.py'], text=True).splitlines()
for f in files:
    py_compile.compile(f, doraise=True)
print(f"Compiled {len(files)} Python files successfully.")
PY
```

Preferred shortcut:

```bash
make check
```

## Code Style

- Prefer clear, explicit names over abbreviations.
- Keep functions focused and side effects local.
- Add docstrings for non-trivial modules/functions.
- Keep comments intent-focused (why), not line-by-line narration (what).
- Preserve backward-compatible CLI behavior unless change is intentional and documented.

## README Standard (Module Level)

Each module README should follow this section order:

1. `# <module_name>`
2. `## Description`
3. `## Usage`
4. `## Arguments`
5. `## Input`
6. `## Output`
7. `## Install`
8. `## Notes` (optional)

Rules:

- Keep commands runnable as-is.
- Match argument names and required flags to `main.py` exactly.
- Use one fenced `bash` block per usage/install section.
- Keep wording concise and implementation-accurate.

## Root README Standard

The root `README.md` should include:

- Overview and supported formats
- Pipeline modules and additional modules with links
- Configuration concept (`process.json` + per-module config)
- Build/setup instructions (Windows and Linux/macOS)
- End-to-end usage examples
- Notes on platform/runtime prerequisites

## Documentation Change Policy

Update documentation in the same PR/commit when:

- CLI arguments change
- Runtime prerequisites change
- Pipeline order or enabled modules change
- Output artifacts or paths change

When in doubt, document the behavior change.
