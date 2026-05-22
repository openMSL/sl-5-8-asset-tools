# Pipeline Modules

The asset extraction pipeline runs modules in a configured order defined by
[`configs/process.json`](../reference/configuration.md). Each module performs
a specific transformation step.

## Execution Order

| # | Module | Purpose | Default |
|---|--------|---------|---------|
| 1 | [pipeline](pipeline.md) | Pipeline entrypoint and orchestrator | — |
| 2 | [metadata_extractor](metadata_extractor.md) | Extract metadata from asset files | ✅ |
| 3 | [jsonld_creator](jsonld_creator.md) | Create JSON-LD from extracted attributes | ✅ |
| 4 | [openlabel_creator](openlabel_creator.md) | Create OpenLABEL JSON from scenario metadata | ✅ |
| 5 | [shacl_combiner](shacl_combiner.md) | Combine referenced SHACL shapes | ✅ |
| 6 | [metadata_enricher](metadata_enricher.md) | Rule-based metadata enrichment | ❌ |
| 7 | [wizard](wizard.md) | Interactive SHACL-driven metadata wizard | ❌ |
| 8 | [quality_checker](quality_checker.md) | ASAM/OpenMSL quality checks | ✅ |
| 9 | [geojson_creator](geojson_creator.md) | Road network + bounding box GeoJSON | ✅ |
| 10 | [preview_3d](preview_3d.md) | 3D preview GeoJSON | ❌ |
| 11 | [search_indexer](search_indexer.md) | XML → binary JSON for search indexing | ✅ |
| 12 | [packager](packager.md) | Final folder structure + manifest | ✅ |

## Pipeline Flow (OpenDRIVE)

```text
input_manifest.json
  → metadata_extractor     → temp/{name}_extractor.json
  → jsonld_creator           → temp/hdmap.json
  → shacl_combiner           → temp/hdmap.ttl
  → wizard (disabled) → metadata/hdmap.json
  → jsonld_validator (OMB)     → validation pass/fail
  → qualitychecker (ASAM)    → validation-reports/{name}_asam_cb_xodr.xqar
  → qualitychecker (OpenMSL) → validation-reports/{name}_openmsl_cb_xodr.xqar
  → geojson_creator     → media/roadNetwork.geojson + media/bbox.geojson
  → preview_3d   → media/3d_preview/*.json
  → search_indexer            → metadata/{name}.bjson
  → packager        → temp/{name}_structure.json
  → jsonld_creator           → manifest.json
  → jsonld_validator (OMB)     → final validation
  → create asset.zip
```
