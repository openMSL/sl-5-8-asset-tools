# Asset Tools

Tools to analyze, transform, and package simulation asset data into
EVES-003 conformant `asset.zip` archives for the
[ENVITED-X Dataspace](https://2getthere.2gether.eu).

The tools are primarily used by the asset service pipeline in
[sl-5-7-asset-services](https://github.com/openMSL/sl-5-7-asset-services).

## Supported Formats

| Format | Extension | Asset Type |
|--------|-----------|------------|
| ASAM OpenDRIVE | `.xodr` | `hdmap` |
| ASAM OpenSCENARIO XML | `.xosc` | `scenario` |
| 3D environment model | `.zip`, `.7z` | `environment-model` |

## Quick Links

- [Setup](getting-started/setup.md) — install and configure the toolchain
- [Quick Start](getting-started/quickstart.md) — generate your first asset
- [Pipeline Modules](modules/index.md) — module reference
- [Input Manifest](reference/input-manifest.md) — manifest format specification
- [Configuration](reference/configuration.md) — pipeline configuration
- [Contributing](contributing.md) — code style, DCO, development workflow

## Process Diagram

![AssetExtractor process](AssetExtractor_process.png)
