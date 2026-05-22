# search_indexer

## Description

Builds a compact binary JSON index from XML asset files for search and filtering in the marketplace.

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
