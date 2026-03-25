# xodr_routing_creator

## Description

Parses OpenDRIVE plan view geometry, reprojects coordinates, and exports georeferenced route/bounding-box files in GeoJSON or KML.

## Usage

```bash
python -m xodr_routing_creator.main <file.xodr> -out <roadNetwork.geojson|kml> [-box <bbox.geojson|kml>]
```

## Arguments

- `filename` (required): OpenDRIVE input file.
- `-out` (required): Output route geometry file. Format is selected by file extension (`.geojson` or `.kml`).
- `-box` (optional): Output bounding-box geometry file (`.geojson` or `.kml`).

## Input

- OpenDRIVE file

## Output

- Route geometry file
- Optional bounding-box geometry file

## Install

```bash
make install  # from repository root
```
