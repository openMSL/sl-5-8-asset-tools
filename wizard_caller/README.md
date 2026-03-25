# wizard_caller

## Description

CLI wizard for enriching JSON-LD metadata using SHACL shape constraints.

Parses a combined SHACL Turtle file to discover required and optional
properties, compares against an existing JSON-LD instance, and prompts
the user to fill in any missing values interactively in the terminal.

When disabled (`-enable false`), simply copies the input JSON-LD to the
output path unchanged.

## Usage

```bash
python -m wizard_caller.main <jsonld_file> -shacl <combined_shacl.ttl> -enable <true|false> -out <enhanced.json>
```

### How It Works

1. Parses the SHACL shapes to discover all `sh:NodeShape` definitions
   and their property constraints (required fields, datatypes, enums).
2. Walks the JSON-LD tree, matching `@type` values to SHACL target classes.
3. For each shape property, checks whether a value already exists.
4. Prompts the user for any missing or incomplete values:
   - `sh:in` constraints → numbered selection menu
   - `sh:datatype` → typed input (text, float, integer, boolean)
   - `sh:node` → recursively processes nested objects
   - `sh:minCount >= 1` → marked as required
5. Writes the enriched JSON-LD to the output path.

## Arguments

- `filename` (required): Input JSON-LD file.
- `-shacl` (required): Combined SHACL Turtle file.
- `-enable` (required): `true` to run the interactive wizard, `false` to copy unchanged.
- `-out` (required): Output JSON-LD file path.

## Input

- JSON-LD instance file (e.g. `hdmap_instance.json`)
- Combined SHACL Turtle file (e.g. `hdmap_instance.ttl`)

## Output

- Enriched JSON-LD file with user-provided values for missing fields

## Install

```bash
make setup  # from repository root
```

## Notes

- This module is currently disabled in the default pipeline configuration (`-enable false`).
- Requires `rdflib` (bundled with project dependencies).
