# jsonLD_validator

## Description
Validates a JSON-LD file against derived shacl constraints.

## Usage
```bash
python -m jsonLD_validator.main <jsonld_file> [-closed]
```

## Arguments
- `filename` (required): JSON-LD file to validate.
- `-closed` (optional): Sets `sh:closed=true` on node shapes before validation to enforce stricter property checks.

## Input
- JSON-LD file

## Output
- Validation result in logs

## Install
```bash
make install  # from repository root
```

## Notes
- In the main pipeline this module is replaced by the ontology-management-base validation suite.
