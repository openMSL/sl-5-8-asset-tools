# Output Structure

The pipeline produces an EVES-003 conformant asset archive with the following
folder structure:

```text
<asset_name>/
├── manifest.json
├── README.md
├── simulation-data/          (isOwner)
│   └── {name}.xodr
├── metadata/                 (isPublic / isRegistered)
│   ├── hdmap.json             (domain metadata)
│   └── {name}.bjson          (reduced binary for indexing)
├── media/                    (isPublic)
│   ├── roadNetwork.geojson
│   ├── bbox.geojson
│   ├── {name}_impression-01.png
│   └── 3d_preview/*.json
├── documentation/            (isPublic)
│   └── {name}_documentation.pdf
├── validation-reports/       (isPublic)
│   ├── {name}_asam_cb_xodr.xqar
│   └── {name}_openmsl_cb_xodr.xqar
└── LICENSE
```

## File Descriptions

| File | Purpose |
|------|---------|
| `manifest.json` | JSON-LD manifest with file inventory, CID hashes, and metadata |
| `README.md` | Human-readable asset description |
| `simulation-data/` | Original asset file(s) |
| `metadata/hdmap.json` | Domain-specific metadata (JSON-LD) |
| `metadata/{name}.bjson` | Binary JSON reduced from XML for search indexing |
| `media/roadNetwork.geojson` | Road network geometry (georeferenced assets only) |
| `media/bbox.geojson` | Bounding box polygon (georeferenced assets only) |
| `media/3d_preview/` | GeoJSON 3D preview layers (when enabled) |
| `validation-reports/` | ASAM and OpenMSL quality checker results |
| `LICENSE` | Asset license file |

## CID Hashing

Each file in the archive is hashed using SHA-256 and encoded as a
CIDv1 (Base32) content identifier. These CIDs are stored in the
`manifest.json` and used for integrity verification in the dataspace.

## Access Roles

Files are tagged with access roles that control visibility in the marketplace:

- **`isOwner`** — only visible to the asset owner (simulation data)
- **`isPublic`** — visible to everyone (media, documentation, reports)
- **`isRegistered`** — visible to registered platform users (services)
