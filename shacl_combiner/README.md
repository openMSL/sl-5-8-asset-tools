# shacl_combiner

## Description
Collects all required shacl shapes referenced by a JSON-LD file and writes a combined turtle (`.ttl`) file.

## Usage
```bash
python -m shacl_combiner.main <jsonld_file> -out <output_dir>
```

## Arguments
- `filename` (required): Input JSON-LD file.
- `-out` (required): Target directory for combined shacl output.

## Input
- JSON-LD file

## Output
- Combined shacl turtle file `<input_stem>.ttl`

## Install
```bash
make install  # from repository root
```
