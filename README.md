# Asset Tools

## Overview

This repository contains tools to analyze, transform, and package asset data into CID-named `.zip` archives for marketplace workflows (for example Envited Marketplace).

The tools are primarily used by the asset service pipeline in:

- <https://github.com/openMSL/sl-5-7-asset-services>

## Supported Formats

- ASAM OpenDRIVE (`.xodr`)
- ASAM OpenSCENARIO XML (`.xosc`)
- 3D environment model archives (`.zip`, `.7z`) with a companion `statistic_3dModel.json` metadata file in the same input folder

## Pipeline Modules

The following modules are used in the asset archive pipeline.

- [asset_extraction](asset_extraction/README.md): Pipeline entrypoint and orchestrator.
- [meta_data_extractor](meta_data_extractor/README.md): Extracts metadata from asset files.
- [jsonLD_creator](jsonLD_creator/README.md): Creates JSON-LD from attribute JSON.
- [shacl_combiner](shacl_combiner/README.md): Combines required shacl shapes.
- [wizard_caller](wizard_caller/README.md): SHACL-driven CLI wizard for enriching JSON-LD interactively (disabled via config by default).
- [jsonLD_validator](jsonLD_validator/README.md): Legacy validator (replaced by ontology-management-base in pipeline).
- [qualitychecker_caller](qualitychecker_caller/README.md): Runs ASAM/OpenMSL quality checkers.
- [xodr_routing_creator](xodr_routing_creator/README.md): Generates route and bounding box geometry.
- [xodr_to_geojson_caller](xodr_to_geojson_caller/README.md): Pure-Python OpenDRIVE to GeoJSON 3D preview converter.
- [asset_reducer](asset_reducer/README.md): Reduces XML asset data for search indexing.
- [structure_creator](structure_creator/README.md): Builds final archive structure and manifest input.

## Additional Modules

- [utils](utils/README.md): Shared helper modules.
- [xodr_calc_box](xodr_calc_box/README.md): Bounding box calculation helper.
- [xodr_trim_to_box](xodr_trim_to_box/README.md): Trim OpenDRIVE by bounding box.
- [ontologie_creator](ontologie_creator/README.md): Generate ontology/shacl from Excel table.

## Process Diagram

![AssetExtractor process](AssetExtractor_process.png)

## Configuration

Pipeline behavior is configured through files in [`configs/`](configs).

There are two configuration types:

1. `process.json`

- Defines module order and activation flags.
- Each item contains:
  - `enable`: activate/deactivate module
  - `filename`: module config filename
  - `extensions`: supported asset extensions

1. Module-specific config (for example `config_meta_data_extractor.json`)

- Defines concrete call parameters for a module.
- Core fields:
  - `name`
  - `environment type`
  - `data folder`
  - `params` (`call`, `input`, `output`, `additional`)

Supported placeholders:

- `path`: output base directory
- `sub_path`: target data subfolder
- `name`: asset filename stem
- `asset_path`: directory containing the input manifest
- `asset_type`: asset domain type (`hdmap`, `scenario`, `environment-model`)

Example:

```json
{
  "name": "xodr_routing_creator",
  "environment type": "python",
  "data folder": "media",
  "params": {
    "call": "xodr_routing_creator.main",
    "output": {
      "-out": "{path}/{sub_path}/roadNetwork.geojson"
    },
    "additional": {
      "-box": "{path}/{sub_path}/bbox.geojson"
    }
  }
}
```

## Build

Python 3.12+ is required.

```bash
git clone https://github.com/openMSL/sl-5-8-asset-tools.git
cd sl-5-8-asset-tools
make setup
```

All dependencies are managed via `pyproject.toml` and installed automatically by `make setup`.
When run from a git checkout, `make setup` also initializes and updates the configured git submodules automatically. Cloning with `--recurse-submodules` still works, but is no longer required.

On Windows, run `make` from Git Bash or another POSIX `sh`-compatible shell.

Run `make help` for the full list of available commands.

## Usage

### Run Example Pipelines

Two ready-to-run examples are included under `examples/`:

```bash
make generate opendrive      # OpenDRIVE example  → examples/OpenDRIVE/output/ + examples/OpenDRIVE/<CID>.zip
make generate openscenario   # OpenSCENARIO example → examples/OpenSCENARIO/output/ + examples/OpenSCENARIO/<CID>.zip
```

### Run Pipeline for a Custom Input Directory

```bash
make generate INPUT_DIR=path/to/input OUTPUT_DIR=path/to/output
```

The `INPUT_DIR` must contain an `input_manifest.json`. This is the mode used by downstream asset repositories (e.g. `hd-map-asset-example`) to delegate pipeline execution.

Each example follows the `input/` → `output/` convention:

- `examples/<name>/input/` — input manifest, simulation data, media, docs, LICENSE
- `examples/<name>/output/` — pipeline-generated EVES-003 asset (gitignored)

By default the pipeline uses concise, stage-oriented logging. To inspect raw
child command lines and full stdout/stderr, set `SL58_LOG_MODE=debug` before
running `make generate ...`.

PowerShell example:

```powershell
$env:SL58_LOG_MODE = "debug"
make generate opendrive
```

## Input Manifest

The pipeline accepts an `input_manifest.json` (JSON-LD) that describes the asset
files, their categories and access roles.  A legacy `uploadedFiles.json` array
format is also supported for backward compatibility.

Minimal `input_manifest.json` example:

```json
{
  "@context": [
    "https://w3id.org/ascs-ev/envited-x/manifest/v5/",
    { "envited-x": "https://w3id.org/ascs-ev/envited-x/envited-x/v3/" }
  ],
  "@id": "did:key:z6Mk...",
  "@type": "envited-x:Manifest",
  "hasArtifacts": [
    {
      "@type": "Link",
      "hasCategory": { "@id": "envited-x:isSimulationData" },
      "hasAccessRole": { "@id": "envited-x:isOwner" },
      "hasFileMetadata": {
        "@type": "FileMetadata",
        "filePath": "my-road.xodr",
        "mimeType": "application/xml"
      }
    }
  ],
  "hasLicense": {
    "@type": "Link",
    "hasCategory": { "@id": "envited-x:isLicense" },
    "hasAccessRole": { "@id": "envited-x:isPublic" },
    "hasFileMetadata": {
      "@type": "FileMetadata",
      "filePath": "LICENSE",
      "mimeType": "text/plain"
    }
  }
}
```

Supported categories:

- `isSimulationData`, `isDocumentation`, `isMedia`, `isMetadata`
- `isValidationReport`, `isLicense`, `isMiscellaneous`

## SD Creation Wizard

The SD Creation Wizard provides a web UI for interactively enriching metadata
using SHACL shapes. It runs as two containers (API + frontend) via Podman.

```bash
make wizard            # installs Podman if needed, builds and starts containers
make wizard stop       # stops the containers
make setup wizard      # install Podman + compose provider only (called by wizard)
```

`make wizard` performs automatic pre-flight checks:
- Installs Podman if missing (via `winget` on Windows, `apt` on Linux)
- Initialises and starts the Podman machine on Windows if needed
- Installs `podman-compose` if no compose provider is found

### Windows first-time setup

The wizard containers require a Linux VM backend. On Windows this means
**WSL2** (recommended) or **Hyper-V** (Windows Pro/Enterprise).

```bash
# Enable WSL2 (admin terminal, reboot required, one-time)
wsl --install --no-distribution

# After reboot, initialise and start the Podman machine
podman machine init
podman machine start
```

Or open **Podman Desktop** from the Start menu -- it will guide you through
the machine setup. Then restart your shell and run `make wizard`.

> **No WSL2 or Hyper-V?** Use the CLI wizard instead:
> ```bash
> python -m wizard_caller.main metadata/hdmap.json -shacl temp/hdmap.ttl -enable true -out metadata/hdmap.json
> ```
> This provides the same SHACL-driven metadata enrichment in the terminal.

### Corporate proxy (Windows)

If you are behind a corporate proxy (e.g. proxydetox, CNTLM, px-proxy) the
Podman WSL VM cannot reach container registries by default because the proxy
typically listens on `127.0.0.1` which is not shared with the VM.

**Step 1 — Bridge the proxy into the VM via SSH tunnel**

```bash
# Find the Podman machine SSH port and identity file
podman system connection list
# Example output:
#   podman-machine-default  ssh://user@127.0.0.1:42475/run/user/1000/podman/podman.sock  C:\Users\you\.local\...

# Open a reverse tunnel (replace port and identity path from above)
ssh -f -N -R 3128:127.0.0.1:3128 \
    -i "C:\Users\you\.local\share\containers\podman\machine\machine" \
    -p 42475 -o StrictHostKeyChecking=no user@127.0.0.1
```

Replace `3128` with your proxy port. The tunnel forwards the VM's
`localhost:3128` to your Windows `localhost:3128`.

**Step 2 — Configure proxy for the Podman service**

```bash
# Create a systemd drop-in for the user-level Podman service
podman machine ssh "
  sudo chown -R \$(whoami) ~/.config/systemd 2>/dev/null
  mkdir -p ~/.config/systemd/user/podman.service.d
  printf '[Service]\nEnvironment=HTTP_PROXY=http://127.0.0.1:3128\nEnvironment=HTTPS_PROXY=http://127.0.0.1:3128\nEnvironment=NO_PROXY=localhost,127.0.0.1\n' \
    > ~/.config/systemd/user/podman.service.d/proxy.conf
  systemctl --user daemon-reload
  systemctl --user restart podman.service
"
```

**Step 3 — Enable proxy pass-through for container builds**

```bash
podman machine ssh "
  mkdir -p ~/.config/containers
  printf '[engine]\nhttp_proxy = true\nenv = [\"HTTP_PROXY=http://127.0.0.1:3128\", \"HTTPS_PROXY=http://127.0.0.1:3128\", \"NO_PROXY=localhost,127.0.0.1\"]\n' \
    > ~/.config/containers/containers.conf
"
```

**Verify** the setup works:

```bash
podman machine ssh "curl -s -o /dev/null -w '%{http_code}' --proxy http://127.0.0.1:3128 https://registry-1.docker.io/v2/"
# Expected output: 401 (authentication required — means the registry is reachable)
```

> **Note:** The SSH tunnel must be re-established after each reboot or Podman
> machine restart. Steps 2 and 3 persist across restarts.

### Ports

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:4200   |
| API      | http://localhost:8080   |

## Notes

- For module-specific usage and parameters, see each module README linked above.
