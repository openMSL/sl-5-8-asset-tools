# Pipeline Modules

The asset extraction pipeline runs modules in a configured order defined by
[`configs/process.json`](../reference/configuration.md). Each module performs
a specific transformation step.

## Execution Order

| # | Module | Purpose | Default |
|---|--------|---------|---------|
| 1 | [asset_extraction](asset_extraction.md) | Pipeline entrypoint and orchestrator | — |
| 2 | [meta_data_extractor](meta_data_extractor.md) | Extract metadata from asset files | ✅ |
| 3 | [jsonLD_creator](jsonLD_creator.md) | Create JSON-LD from extracted attributes | ✅ |
| 4 | [openlabel_creator](openlabel_creator.md) | Create OpenLABEL JSON from scenario metadata | ✅ |
| 5 | [shacl_combiner](shacl_combiner.md) | Combine referenced SHACL shapes | ✅ |
| 6 | [llm_enricher](llm_enricher.md) | Rule-based metadata enrichment | ❌ |
| 7 | [wizard_caller](wizard_caller.md) | Interactive SHACL-driven metadata wizard | ❌ |
| 8 | [qualitychecker_caller](qualitychecker_caller.md) | ASAM/OpenMSL quality checks | ✅ |
| 9 | [xodr_routing_creator](xodr_routing_creator.md) | Road network + bounding box GeoJSON | ✅ |
| 10 | [xodr_to_geojson_caller](xodr_to_geojson_caller.md) | 3D preview GeoJSON | ❌ |
| 11 | [asset_reducer](asset_reducer.md) | XML → binary JSON for search indexing | ✅ |
| 12 | [structure_creator](structure_creator.md) | Final folder structure + manifest | ✅ |

## Pipeline Flow (OpenDRIVE)

```text
input_manifest.json
  → meta_data_extractor     → temp/{name}_extractor.json
  → jsonLD_creator           → temp/hdmap.json
  → shacl_combiner           → temp/hdmap.ttl
  → wizard_caller (disabled) → metadata/hdmap.json
  → jsonLD_validator_omb     → validation pass/fail
  → qualitychecker (ASAM)    → validation-reports/{name}_asam_cb_xodr.xqar
  → qualitychecker (OpenMSL) → validation-reports/{name}_openmsl_cb_xodr.xqar
  → xodr_routing_creator     → media/roadNetwork.geojson + media/bbox.geojson
  → xodr_to_geojson_caller   → media/3d_preview/*.json
  → asset_reducer            → metadata/{name}.bjson
  → structure_creator        → temp/{name}_structure.json
  → jsonLD_creator           → manifest.json
  → jsonLD_validator_omb     → final validation
  → create asset.zip
```
