# Input Manifest

The pipeline accepts an `input_manifest.json` (JSON-LD) that describes the
asset files, their categories and access roles.

## Generating a Manifest Automatically

If you don't have an `input_manifest.json` yet, generate one from your files:

```bash
make init INPUT_DIR=path/to/my-asset
```

This scans the directory for simulation data (`.xodr`, `.xosc`, `.zip`, `.7z`),
documentation, media, and license files, then writes an `input_manifest.json`
ready for the pipeline.

Use `FORCE=true` to overwrite an existing manifest.

## Manifest Format

Minimal example:

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

## Categories

| Category | Purpose |
|----------|---------|
| `isSimulationData` | Primary asset files (`.xodr`, `.xosc`, `.zip`) |
| `isDocumentation` | PDF, text, or markdown documentation |
| `isMedia` | Images, videos, companion JSON |
| `isMetadata` | Domain metadata files |
| `isValidationReport` | Quality check reports |
| `isLicense` | License file |
| `isMiscellaneous` | Anything else |

## Access Roles

| Role | Visibility | Typical Use |
|------|------------|-------------|
| `isOwner` | Owner only | Simulation data |
| `isPublic` | Public | Media, documentation, reports |
| `isRegistered` | Registered users | Services |
