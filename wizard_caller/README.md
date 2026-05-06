# wizard_caller

## Description

Pipeline module for interactive metadata enrichment using SHACL shapes.

Supports three modes:

- **Browser mode** (default when `WIZARD=true`): Opens a browser-based wizard UI
  pre-filled with auto-extracted metadata. The pipeline pauses until the user
  clicks Export.
- **CLI mode** (fallback): Terminal-based SHACL wizard with rdflib prompts.
- **Disabled** (default): Simply copies input JSON-LD to output unchanged.

## Usage

### As part of the pipeline (recommended)

```bash
WIZARD=true make generate INPUT_DIR=path/to/input
```

The wizard auto-starts (API + frontend), opens the browser, and waits for export.

### Standalone

```bash
python -m wizard_caller.main <jsonld_file> -shacl <combined_shacl.ttl> -enable <true|false> -out <enhanced.json>
```

### Environment Variables

| Variable | Effect |
|----------|--------|
| `WIZARD_ENABLED=true` | Activates wizard even when config says `-enable false` |
| `WIZARD_API_URL` | Override API URL (default: `http://localhost:3007`) |
| `WIZARD_FRONTEND_URL` | Override frontend URL (default: `http://localhost:4200`) |

## Arguments

- `filename` (required): Input JSON-LD file.
- `-shacl` (required): Combined SHACL Turtle file.
- `-enable` (required): `true` to run the interactive wizard, `false` to copy unchanged.
- `-out` (required): Output JSON-LD file path.
- `-api-url` (optional): Wizard API URL.
- `-frontend-url` (optional): Wizard frontend URL.

## Input

- JSON-LD instance file (e.g. `temp/hdmap.json`)
- Combined SHACL Turtle file (e.g. `temp/hdmap.ttl`)

## Output

- Enriched JSON-LD file with user-provided values for missing fields (e.g. `metadata/hdmap.json`)

## Install

```bash
make setup  # installs Python + wizard (Node.js) dependencies
```

## How It Works

### Browser Mode (API available)

1. Ensures the wizard API + frontend are running (auto-starts if needed)
2. Creates a session via `POST /session` with SHACL + JSON-LD files
3. Opens the browser — frontend auto-loads the session
4. Polls `GET /session/status` until user clicks Export (10 min timeout)
5. Writes exported JSON-LD to the output path

### CLI Mode (fallback)

1. Parses SHACL shapes to discover `sh:NodeShape` definitions and constraints
2. Walks the JSON-LD tree, matching `@type` values to SHACL target classes
3. Prompts for missing values (selection menus, typed input, nested objects)
4. Writes the enriched JSON-LD to the output path
