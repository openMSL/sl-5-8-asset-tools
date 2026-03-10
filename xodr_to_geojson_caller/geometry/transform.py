"""CRS transformation: project coordinates from OpenDRIVE source CRS to WGS84."""

from __future__ import annotations

from pyproj import CRS, Transformer

Coord3D = tuple[float, float, float]

# WGS84 geographic CRS (standard for GeoJSON)
WGS84 = CRS.from_epsg(4326)


def create_transformer(source_proj4: str) -> Transformer | None:
    """Create a pyproj Transformer from a proj4 string to WGS84.

    Returns None if the proj4 string is empty or invalid.
    """
    if not source_proj4.strip():
        return None
    try:
        source_crs = CRS.from_proj4(source_proj4)
        return Transformer.from_crs(source_crs, WGS84, always_xy=True)
    except Exception:
        return None


def transform_coord(
    coord: Coord3D, transformer: Transformer | None
) -> Coord3D:
    """Transform a single 3D coordinate. Pass-through if no transformer."""
    if transformer is None:
        return coord
    x, y, z = coord
    lon, lat = transformer.transform(x, y)
    return (lon, lat, z)


def transform_coords(
    coords: list[Coord3D], transformer: Transformer | None
) -> list[Coord3D]:
    """Transform a list of 3D coordinates."""
    if transformer is None:
        return coords
    return [transform_coord(c, transformer) for c in coords]
