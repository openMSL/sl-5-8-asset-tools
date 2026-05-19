---
title: preview_3d
---

# preview_3d

## Description

Pure-Python OpenDRIVE (.xodr) to GeoJSON converter. Re-implements the
[VCS opendriveconverter](https://github.com/virtualcitySYSTEMS/opendriveconverter)
(Java) entirely in Python, removing the Java runtime dependency.

## Usage

```bash
python -m preview_3d.main <file.xodr> -out <output_dir>
```

## Arguments

- `filename` (required): OpenDRIVE input file (.xodr).
- `-out` (required): Output directory for GeoJSON files.
- `-path` (optional): Unused, kept for pipeline backward compatibility.
- `-step` (optional): Discretisation step in meters (default: 0.2).

## Input

- OpenDRIVE `.xodr` file (ASAM OpenDRIVE 1.4–1.8)

## Output

- `refLine.json` — Road reference lines (LineString)
- `breakLines.json` — Lane boundary lines (LineString)
- `roads.json` — Road polygons
- `lanes.json` — Individual lane polygons
- `laneSections.json` — Lane section polygons
- `objects.json` — Road objects (Point/Polygon)
- `signals.json` — Traffic signals (Point)
- `roadMarks.json` — Road marking polygons
- `junctions.json` — Junction areas (MultiPolygon)

## Supported OpenDRIVE Geometry Types

- Line, Arc, Spiral (clothoid), Poly3, ParamPoly3

## Install

```bash
make install  # from repository root
```

## Tests

```bash
python -m pytest preview_3d/tests/ -v
```
