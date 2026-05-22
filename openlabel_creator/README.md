# openlabel_creator

## Description

Discovers OpenLABEL JSON companion files for scenario assets and
transforms them into JSON-LD conforming to the OpenLABEL v2 `TagShape`.
Tags are categorized using the ASAM OpenLABEL taxonomy
(`tag_categories.py`) and injected into the scenario metadata.

Uses compact JSON-LD notation based on `@vocab` context from the
`openlabel-v2` ontology (`https://w3id.org/ascs-ev/envited-x/openlabel/v2/`).

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

- JSON-LD with `Tag` instances (OpenLABEL v2 compact notation)

## Install

```bash
make install  # from repository root
```
