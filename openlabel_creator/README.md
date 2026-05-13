# openlabel_creator

## Description

Discovers OpenLABEL JSON companion files for scenario assets and
transforms them into JSON-LD conforming to `openlabel:TagShape`.
Tags are categorized using the ASAM OpenLABEL taxonomy
(`tag_categories.py`) and injected into the scenario metadata.

## Usage

```bash
python -m openlabel_creator --input <openlabel.json> --output <openlabel.jsonld>
```

## Arguments

- `-out` (required): Output JSON-LD file path.
- `-inject` (optional): Existing JSON-LD file to inject tags into.

## Input

- OpenLABEL JSON file (auto-discovered from input manifest)

## Output

- JSON-LD with `openlabel:Tag` instances

## Install

```bash
make install  # from repository root
```
