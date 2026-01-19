Map and Scenario Data
====

## Description
This repository contains all the tools of the data providers. These tools are mostly called up in https://github.com/openMSL/sl-5-7-asset-services in the Docker as a pipeline to automatically generate an asset.zip from an asset.
Most of the tools of Asset Extractor supports the following formats:
- ASAM OpenDRIVE
- ASAM OpenSCENARI XML
- 3D Envirenment model (with metadata json input from Trian3DBuilder)

### Content

```
├── asset_extraction: extracts, analyzes the assert and brings all information together in an asset archive
├── asset_reducer: reduces the xml based asset file to relevant nodes and attributes for the advanced search. see provider-services repro
├── configs - config file to control the call in the asset extractor
├── jsonLD_creator: creates a jsonLD from a json file with the help of ontology files.
├── jsonLD_validator: validate jsonLD against shacls
├── meta_data_extractor: extracts meta data for the asset product description
├── ontology_creator: creates an ontology and shacl file from an excel table
├── qualitychecker_caller: call ASAM and OpenMSL QualityChecker bundles to validate OpenDRIVE and OpenSCENARIO
├── shacl_combiner: combines all required GAIAX Shacls to a Shalc to use them for example in the SD Creation Wizard or in Shalc Playgrounds
├── structure_creator: creates a folder and file structure for the asset archive and writes the structure to a json file (for the creation of the manifest jsonLD)
├── wizard-caller: calls up the SD Creation Wizard with the prefabricated claim and combined Shacl to complete the claim file
├── xodr_calc_box: calculate boundinb box of OpenDRIVE file
├── xodr_routing_creator: creates a routing file (KML or GeoJSON) to display the asset geographically in map applications.
├── xodr_to_geojson_caller: calls up vcs-odr-converter java file to create 3d preview geojson files for OpenDRIVE
├── xodr_trim_to_box: reduce OpenDRIVE file to given boundingbox
├── CONTRIBUTING.md
├── LICENSE.md
├── Readme.md
```

![AsssetExtractor process](AssetExtractor_process.png)


