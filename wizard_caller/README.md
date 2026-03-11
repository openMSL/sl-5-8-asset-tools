# wizard_caller

## Description
Integrates with the SD Creation Wizard service to enrich JSON-LD with user-provided values.

## Usage
```bash
python -m wizard_caller.main <jsonld_file> -shacl <combined_shacl.ttl> -enable <true|false> -out <enhanced.json>
```

## Arguments
- `filename` (required): Input JSON-LD file.
- `-shacl` (required): Combined shacl file.
- `-enable` (required): If `true`, call wizard endpoints; if `false`, copy input to output.
- `-out` (required): Output JSON-LD file path.

## Input
- JSON-LD file
- Combined shacl file

## Output
- Enhanced JSON-LD file

## Install
```bash
make install  # from repository root
```

## Notes
- This module is currently disabled in the default pipeline configuration.
