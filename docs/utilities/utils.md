---
title: utils
---

# utils

## Description

Shared helper modules used across tools.

Current utilities include:

- `utils.log_config`: Logging setup and subprocess output formatting.
- `utils.subprocess`: Wrapper for consistent subprocess execution/logging.
- `utils.json`: JSON/pickle read-write helpers and path normalization.
- `utils.http`: URL and download helpers.
- `utils.rdf`: RDF/JSON-LD helper functions.
- `utils.ids`: ID/UUID helper logic.
- `utils.geometry`: Geometry primitives and helpers.
- `utils.xodr`: OpenDRIVE parsing helpers.
- `utils.constants`: Shared constants.

## Usage

```bash
python -c "import utils"
```

## Arguments

- None (library module, no CLI entrypoint).

## Input

- Python imports from pipeline modules.

## Output

- Reusable helper functions/classes for other modules.

## Install

```bash
make install  # from repository root
```
