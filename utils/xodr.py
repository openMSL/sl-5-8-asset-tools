from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple

from .geometry import Vec2D


def parse_planview(
    file_path: Path | str,
) -> tuple[Optional[str], Vec2D, List[List[Tuple[float, float, float, float]]]]:
    """Parse an OpenDRIVE file and extract geoReference proj4, offset and planView geometries."""
    tree = ET.parse(str(file_path))
    root = tree.getroot()

    georef = root.find(".//geoReference")
    proj4_str: Optional[str] = (
        georef.text.strip() if (georef is not None and georef.text) else None
    )

    offset_node = root.find(".//offset")
    offset = Vec2D(0, 0)
    if offset_node is not None:
        offset = Vec2D(
            float(offset_node.attrib.get("x", 0.0)),
            float(offset_node.attrib.get("y", 0.0)),
        )

    lines: List[List[Tuple[float, float, float, float]]] = []
    for line in root.findall(".//planView"):
        coordinates: List[Tuple[float, float, float, float]] = []
        for point in line.findall(".//geometry"):
            x = float(point.attrib["x"])
            y = float(point.attrib["y"])
            hdg = float(point.attrib["hdg"])
            length = float(point.attrib["length"])
            coordinates.append((x, y, hdg, length))
        lines.append(coordinates)

    return proj4_str, offset, lines
