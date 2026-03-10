"""GeoJSON converter: builds FeatureCollections from OpenDRIVE data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pyproj import Transformer

from xodr_to_geojson_caller.generators.object import generate_object_geometries
from xodr_to_geojson_caller.generators.road import (
    generate_center_line,
    generate_lane_ground_points,
    generate_lane_polygons,
    generate_road_polygon,
)
from xodr_to_geojson_caller.generators.roadmark import generate_road_mark_points
from xodr_to_geojson_caller.generators.signal import generate_signal_points
from xodr_to_geojson_caller.geometry.transform import (
    create_transformer,
    transform_coord,
    transform_coords,
)
from xodr_to_geojson_caller.models.opendrive import OpenDRIVE

logger = logging.getLogger(__name__)

Coord3D = tuple[float, float, float]


def _feature(geometry_type: str, coordinates: Any, properties: dict) -> dict:
    """Create a GeoJSON Feature dict."""
    return {
        "type": "Feature",
        "geometry": {
            "type": geometry_type,
            "coordinates": [list(c) for c in coordinates]
            if isinstance(coordinates, list)
            else list(coordinates),
        },
        "properties": properties,
    }


def _polygon_feature(coordinates: list[Coord3D], properties: dict) -> dict:
    """Create a GeoJSON Polygon Feature (wraps coords in outer ring array)."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[list(c) for c in coordinates]],
        },
        "properties": properties,
    }


def _feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _write_geojson(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    logger.info("Wrote %s (%d features)", path, len(data.get("features", [])))


# --- Converter functions ---


def convert_reference_lines(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert reference lines (center lane) of all roads."""
    features = []
    for road in odr.roads:
        points = generate_center_line(road, step=step)
        points = transform_coords(points, transformer)
        features.append(_feature(
            "LineString", points,
            {"roadId": road.id, "name": road.name, "length": road.length},
        ))
    return _feature_collection(features)


def convert_lanes(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert individual lane polygons."""
    features = []
    for road in odr.roads:
        for ls in road.lanes.lane_sections:
            bp = generate_lane_ground_points(road, ls, step=step)
            polys = generate_lane_polygons(ls, bp)
            for lane_id, coords in polys:
                coords = transform_coords(coords, transformer)
                # Find the lane object for metadata
                lane = next(
                    (l for l in ls.all_lanes if l.id == lane_id), None
                )
                features.append(_polygon_feature(coords, {
                    "roadId": road.id,
                    "laneId": lane_id,
                    "type": lane.type if lane else "",
                    "sOffset": ls.s,
                }))
    return _feature_collection(features)


def convert_lane_sections(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert lane section polygons (all lanes merged per section)."""
    features = []
    for road in odr.roads:
        for ls in road.lanes.lane_sections:
            bp = generate_lane_ground_points(road, ls, step=step)
            coords = generate_road_polygon(ls, bp)
            if coords:
                coords = transform_coords(coords, transformer)
                features.append(_polygon_feature(coords, {
                    "roadId": road.id,
                    "sOffset": ls.s,
                }))
    return _feature_collection(features)


def convert_roads(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert overall road polygons."""
    features = []
    for road in odr.roads:
        all_coords: list[Coord3D] = []
        for ls in road.lanes.lane_sections:
            bp = generate_lane_ground_points(road, ls, step=step)
            rp = generate_road_polygon(ls, bp)
            if rp:
                all_coords = rp  # Use last (or only) section as road polygon
        if all_coords:
            all_coords = transform_coords(all_coords, transformer)
            features.append(_polygon_feature(all_coords, {
                "roadId": road.id,
                "name": road.name,
                "length": road.length,
                "junction": road.junction,
            }))
    return _feature_collection(features)


def convert_lane_break_lines(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert lane boundary lines."""
    features = []
    for road in odr.roads:
        for ls in road.lanes.lane_sections:
            bp = generate_lane_ground_points(road, ls, step=step)
            for lane_id, points in bp.items():
                points = transform_coords(points, transformer)
                features.append(_feature(
                    "LineString", points,
                    {"roadId": road.id, "laneId": lane_id, "sOffset": ls.s},
                ))
    return _feature_collection(features)


def convert_objects(
    odr: OpenDRIVE, transformer: Transformer | None = None
) -> dict:
    """Convert road objects to GeoJSON features."""
    features = []
    for road in odr.roads:
        for geom_type, coords, props in generate_object_geometries(road):
            props["roadId"] = road.id
            if geom_type == "Point":
                coords = transform_coord(coords, transformer)
                features.append(_feature("Point", coords, props))
            elif geom_type == "Polygon":
                coords = transform_coords(coords, transformer)
                features.append(_polygon_feature(coords, props))
    return _feature_collection(features)


def convert_signals(
    odr: OpenDRIVE, transformer: Transformer | None = None
) -> dict:
    """Convert signals to GeoJSON point features."""
    features = []
    for road in odr.roads:
        for coords, props in generate_signal_points(road):
            props["roadId"] = road.id
            coords = transform_coord(coords, transformer)
            features.append(_feature("Point", coords, props))
    return _feature_collection(features)


def convert_road_marks(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert road markings to GeoJSON polygon features."""
    features = []
    for road in odr.roads:
        for ls in road.lanes.lane_sections:
            segments = generate_road_mark_points(road, ls, step=step)
            for mark_type, lane_id, inner, outer in segments:
                # Build polygon from inner + reversed outer
                ring = inner + list(reversed(outer))
                ring.append(ring[0])
                ring = transform_coords(ring, transformer)
                features.append(_polygon_feature(ring, {
                    "roadId": road.id,
                    "laneId": lane_id,
                    "markType": mark_type,
                    "sOffset": ls.s,
                }))
    return _feature_collection(features)


def convert_junctions(
    odr: OpenDRIVE, transformer: Transformer | None = None, step: float = 0.2
) -> dict:
    """Convert junctions to GeoJSON MultiPolygon features.

    A junction aggregates the polygons of all its connecting roads.
    """
    features = []
    road_map = {r.id: r for r in odr.roads}

    for junction in odr.junctions:
        multi_polygons: list[list[list[Coord3D]]] = []
        for conn in junction.connections:
            road = road_map.get(conn.connecting_road)
            if road is None:
                continue
            for ls in road.lanes.lane_sections:
                bp = generate_lane_ground_points(road, ls, step=step)
                rp = generate_road_polygon(ls, bp)
                if rp:
                    rp = transform_coords(rp, transformer)
                    multi_polygons.append([[list(c) for c in rp]])

        if multi_polygons:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": multi_polygons,
                },
                "properties": {"junctionId": junction.id, "name": junction.name},
            })

    return _feature_collection(features)


# --- Main conversion orchestrator ---

CONVERTERS = {
    "refLine.json": convert_reference_lines,
    "breakLines.json": convert_lane_break_lines,
    "roads.json": convert_roads,
    "lanes.json": convert_lanes,
    "laneSections.json": convert_lane_sections,
    "objects.json": convert_objects,
    "signals.json": convert_signals,
    "roadMarks.json": convert_road_marks,
    "junctions.json": convert_junctions,
}


def convert_all(
    odr: OpenDRIVE,
    output_dir: Path,
    step: float = 0.2,
) -> None:
    """Run all converters and write GeoJSON files to output_dir."""
    transformer = create_transformer(odr.header.geo_reference.proj4)

    for filename, converter in CONVERTERS.items():
        try:
            if converter in (convert_objects, convert_signals):
                fc = converter(odr, transformer=transformer)
            else:
                fc = converter(odr, transformer=transformer, step=step)
            _write_geojson(fc, output_dir / filename)
        except Exception:
            logger.exception("Failed to convert %s", filename)
