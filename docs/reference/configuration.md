# Configuration

Pipeline behavior is configured through files in `configs/`.

## Configuration Types

### Process Configuration (`process.json`)

Defines which modules run, their execution order, enabled/disabled state,
and which file extensions they support:

```json
{
  "metadata_extractor": {
    "enable": true,
    "extensions": ["xodr", "xosc"]
  }
}
```

### Module Configuration (`config_<module>.json`)

Per-module settings with call parameters, input/output paths, and
placeholders:

```json
{
  "name": "geojson_creator",
  "call": "geojson_creator.main",
  "output": {
    "-out": "{path}/{sub_path}/roadNetwork.geojson"
  },
  "additional": {
    "-box": "{path}/{sub_path}/bbox.geojson"
  }
}
```

## Placeholders

Module configs support these placeholders that are resolved at runtime:

| Placeholder | Expands to |
|-------------|------------|
| `{path}` | Output directory path |
| `{sub_path}` | Target data subfolder (from config `"data folder"`) |
| `{name}` | Asset filename stem (no extension) |
| `{asset_path}` | Full path to asset file |
| `{asset_type}` | Asset type string (`hdmap`, `scenario`, `environment-model`) |

## Runtime Flags

### Module Selection

```bash
# Disable a module
make generate opendrive PIPELINE_FLAGS="-disable geojson_creator"

# Enable only specific modules
make generate opendrive PIPELINE_FLAGS="-enable metadata_extractor packager"

# List module IDs
make generate opendrive PIPELINE_FLAGS="-list-modules"
```

### Wizard

Enable the interactive wizard during pipeline runs:

```bash
WIZARD=true make generate opendrive
```

### Debug Logging

```bash
SL58_LOG_MODE=debug make generate opendrive
```
