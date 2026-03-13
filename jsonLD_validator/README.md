# jsonLD_validator

## Description
Deprecated compatibility wrapper around the
`ontology-management-base` validation suite.

## Usage
```bash
python -m jsonLD_validator.main <jsonld_file>
```

## Arguments
- `filename` (required): JSON-LD file to validate.

## Input
- JSON-LD file

## Output
- Validation result in logs

## Install
```bash
make install  # from repository root
```

## Notes
- In the main pipeline this module is already replaced by the
  `ontology-management-base` validation suite.
- The deprecated `-closed` option is no longer supported. Use
  `python -m src.tools.validators.validation_suite` directly for
  advanced validation workflows.
