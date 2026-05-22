---
title: search_indexer
---

# search_indexer

## Description

Reduces XML-based asset files to relevant nodes/attributes and writes a binary JSON (`pickle`) for extended search.

## Usage

```bash
python -m search_indexer.main <asset.xml> -out <output.bjson>
```

## Arguments

- `filename` (required): Input XML asset file (for example `.xodr`, `.xosc`).
- `-out` (required): Output filename for the reduced binary JSON.

## Input

- XML asset file
- Mapping table from `search_indexer/mapping_tables/`

## Output

- Reduced binary JSON file (`.bjson`)

## Install

```bash
make install  # from repository root
```
