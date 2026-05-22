---
title: jsonld_creator
---

# jsonld_creator

## Description

Creates JSON-LD from an extracted attribute JSON and ontology/shacl sources.

## Usage

```bash
python -m jsonld_creator.main <attributes.json> -ontology <ontology_base_url> -out <output.json> [-removeShacl]
```

## Arguments

- `filename` (required): Input attribute table JSON (for example extractor or structure output).
- `-ontology` (required): Base URL/path to ontologies. Supports `{schema}` placeholder.
- `-out` (required): Output JSON-LD file.
- `-removeShacl` (optional): Remove local shacl cache folder before regeneration.

## Input

- Attribute JSON file
- Ontology and shacl resources

## Output

- Generated JSON-LD file

## Install

```bash
make install  # from repository root
```
