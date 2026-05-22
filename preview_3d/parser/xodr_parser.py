"""OpenDRIVE XML parser: lxml-based parsing into dataclass model."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from preview_3d.models.geometry import (
    Arc,
    Geometry,
    Line,
    ParamPoly3,
    Poly3,
    Spiral,
)
from preview_3d.models.junction import (
    Junction,
    JunctionConnection,
    JunctionLaneLink,
)
from preview_3d.models.lane import (
    Lane,
    LaneHeight,
    LaneOffset,
    LaneSection,
    Lanes,
    LaneWidth,
)
from preview_3d.models.object import (
    CornerLocal,
    CornerRoad,
    ObjectRepeat,
    Outline,
    RoadObject,
)
from preview_3d.models.opendrive import GeoReference, Header, OpenDRIVE
from preview_3d.models.road import (
    ElevationProfile,
    LateralProfile,
    Polynomial,
    Road,
)
from preview_3d.models.roadmark import RoadMark
from preview_3d.models.signal import Signal


def _float(elem: etree._Element, attr: str, default: float = 0.0) -> float:
    val = elem.get(attr)
    return float(val) if val is not None else default


def _int(elem: etree._Element, attr: str, default: int = 0) -> int:
    val = elem.get(attr)
    return int(val) if val is not None else default


def _str(elem: etree._Element, attr: str, default: str = "") -> str:
    val = elem.get(attr)
    return val if val is not None else default


def _strip_ns(tag) -> str | None:
    """Remove XML namespace prefix from tag name.

    Returns None for non-element nodes (comments, PIs) where tag is callable.
    """
    if not isinstance(tag, str):
        return None
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find(elem: etree._Element, tag: str) -> etree._Element | None:
    """Find child element, ignoring namespaces."""
    for child in elem:
        if _strip_ns(child.tag) == tag:
            return child
    return None


def _findall(elem: etree._Element, tag: str) -> list[etree._Element]:
    """Find all child elements with given tag, ignoring namespaces."""
    return [child for child in elem if _strip_ns(child.tag) == tag]


# --- Parsing functions ---


def _parse_geometry(geom_elem: etree._Element) -> Geometry:
    """Parse a <geometry> element with its type-specific child."""
    base = dict(
        s=_float(geom_elem, "s"),
        x=_float(geom_elem, "x"),
        y=_float(geom_elem, "y"),
        hdg=_float(geom_elem, "hdg"),
        length=_float(geom_elem, "length"),
    )

    for child in geom_elem:
        tag = _strip_ns(child.tag)
        if tag == "line":
            return Line(**base)
        elif tag == "arc":
            return Arc(**base, curvature=_float(child, "curvature"))
        elif tag == "spiral":
            return Spiral(
                **base,
                curv_start=_float(child, "curvStart"),
                curv_end=_float(child, "curvEnd"),
            )
        elif tag == "poly3":
            return Poly3(
                **base,
                a=_float(child, "a"),
                b=_float(child, "b"),
                c=_float(child, "c"),
                d=_float(child, "d"),
            )
        elif tag == "paramPoly3":
            return ParamPoly3(
                **base,
                a_u=_float(child, "aU"),
                b_u=_float(child, "bU"),
                c_u=_float(child, "cU"),
                d_u=_float(child, "dU"),
                a_v=_float(child, "aV"),
                b_v=_float(child, "bV"),
                c_v=_float(child, "cV"),
                d_v=_float(child, "dV"),
                p_range=_str(child, "pRange", "arcLength"),
            )

    # Default to line if no child type found
    return Line(**base)


def _parse_polynomial(elem: etree._Element) -> Polynomial:
    return Polynomial(
        s=_float(elem, "s"),
        a=_float(elem, "a"),
        b=_float(elem, "b"),
        c=_float(elem, "c"),
        d=_float(elem, "d"),
    )


def _parse_road_mark(elem: etree._Element) -> RoadMark:
    return RoadMark(
        s_offset=_float(elem, "sOffset"),
        type=_str(elem, "type", "none"),
        weight=_str(elem, "weight"),
        color=_str(elem, "color", "standard"),
        width=_float(elem, "width"),
        lane_change=_str(elem, "laneChange"),
        material=_str(elem, "material"),
        height=_float(elem, "height"),
    )


def _parse_lane(elem: etree._Element) -> Lane:
    return Lane(
        id=_int(elem, "id"),
        type=_str(elem, "type"),
        level=_str(elem, "level") == "true",
        widths=[
            LaneWidth(
                s_offset=_float(w, "sOffset"),
                a=_float(w, "a"),
                b=_float(w, "b"),
                c=_float(w, "c"),
                d=_float(w, "d"),
            )
            for w in _findall(elem, "width")
        ],
        heights=[
            LaneHeight(
                s_offset=_float(h, "sOffset"),
                inner=_float(h, "inner"),
                outer=_float(h, "outer"),
            )
            for h in _findall(elem, "height")
        ],
        road_marks=[_parse_road_mark(rm) for rm in _findall(elem, "roadMark")],
    )


def _parse_lane_section(elem: etree._Element) -> LaneSection:
    left_elem = _find(elem, "left")
    center_elem = _find(elem, "center")
    right_elem = _find(elem, "right")

    left_lanes = (
        [_parse_lane(l) for l in _findall(left_elem, "lane")]
        if left_elem is not None
        else []
    )
    center_lane = (
        _parse_lane(_findall(center_elem, "lane")[0])
        if center_elem is not None and _findall(center_elem, "lane")
        else Lane(id=0)
    )
    right_lanes = (
        [_parse_lane(l) for l in _findall(right_elem, "lane")]
        if right_elem is not None
        else []
    )

    return LaneSection(
        s=_float(elem, "s"),
        left_lanes=left_lanes,
        center_lane=center_lane,
        right_lanes=right_lanes,
    )


def _parse_object(elem: etree._Element) -> RoadObject:
    outlines = []
    outlines_elem = _find(elem, "outlines")
    if outlines_elem is not None:
        for outline_elem in _findall(outlines_elem, "outline"):
            outlines.append(
                Outline(
                    corner_road=[
                        CornerRoad(
                            s=_float(cr, "s"),
                            t=_float(cr, "t"),
                            dz=_float(cr, "dz"),
                            height=_float(cr, "height"),
                        )
                        for cr in _findall(outline_elem, "cornerRoad")
                    ],
                    corner_local=[
                        CornerLocal(
                            u=_float(cl, "u"),
                            v=_float(cl, "v"),
                            z=_float(cl, "z"),
                            height=_float(cl, "height"),
                        )
                        for cl in _findall(outline_elem, "cornerLocal")
                    ],
                )
            )

    repeats = [
        ObjectRepeat(
            s=_float(r, "s"),
            length=_float(r, "length"),
            distance=_float(r, "distance"),
            t_start=_float(r, "tStart"),
            t_end=_float(r, "tEnd"),
            width_start=_float(r, "widthStart"),
            width_end=_float(r, "widthEnd"),
            z_offset_start=_float(r, "zOffsetStart"),
            z_offset_end=_float(r, "zOffsetEnd"),
        )
        for r in _findall(elem, "repeat")
    ]

    return RoadObject(
        id=_str(elem, "id"),
        name=_str(elem, "name"),
        type=_str(elem, "type"),
        s=_float(elem, "s"),
        t=_float(elem, "t"),
        z_offset=_float(elem, "zOffset"),
        hdg=_float(elem, "hdg"),
        length=_float(elem, "length"),
        width=_float(elem, "width"),
        radius=_float(elem, "radius"),
        height=_float(elem, "height"),
        orientation=_str(elem, "orientation"),
        valid_length=_float(elem, "validLength"),
        subtype=_str(elem, "subtype"),
        outlines=outlines,
        repeats=repeats,
    )


def _parse_signal(elem: etree._Element) -> Signal:
    return Signal(
        id=_str(elem, "id"),
        name=_str(elem, "name"),
        type=_str(elem, "type"),
        subtype=_str(elem, "subtype"),
        s=_float(elem, "s"),
        t=_float(elem, "t"),
        z_offset=_float(elem, "zOffset"),
        hdg=_float(elem, "hOffset"),
        orientation=_str(elem, "orientation"),
        value=_float(elem, "value"),
        dynamic=_str(elem, "dynamic"),
        country=_str(elem, "country"),
    )


def _parse_road(road_elem: etree._Element) -> Road:
    # PlanView
    plan_view_elem = _find(road_elem, "planView")
    plan_view = (
        [_parse_geometry(g) for g in _findall(plan_view_elem, "geometry")]
        if plan_view_elem is not None
        else []
    )

    # ElevationProfile
    elev_elem = _find(road_elem, "elevationProfile")
    elevations = (
        [_parse_polynomial(e) for e in _findall(elev_elem, "elevation")]
        if elev_elem is not None
        else []
    )

    # LateralProfile
    lat_elem = _find(road_elem, "lateralProfile")
    super_elevations = (
        [_parse_polynomial(se) for se in _findall(lat_elem, "superelevation")]
        if lat_elem is not None
        else []
    )

    # Lanes
    lanes_elem = _find(road_elem, "lanes")
    lane_offsets = []
    lane_sections = []
    if lanes_elem is not None:
        lane_offsets = [
            LaneOffset(
                s=_float(lo, "s"),
                a=_float(lo, "a"),
                b=_float(lo, "b"),
                c=_float(lo, "c"),
                d=_float(lo, "d"),
            )
            for lo in _findall(lanes_elem, "laneOffset")
        ]
        lane_sections = [
            _parse_lane_section(ls) for ls in _findall(lanes_elem, "laneSection")
        ]

    # Objects
    objects_elem = _find(road_elem, "objects")
    objects = (
        [_parse_object(o) for o in _findall(objects_elem, "object")]
        if objects_elem is not None
        else []
    )

    # Signals
    signals_elem = _find(road_elem, "signals")
    signals = (
        [_parse_signal(s) for s in _findall(signals_elem, "signal")]
        if signals_elem is not None
        else []
    )

    return Road(
        id=_str(road_elem, "id"),
        name=_str(road_elem, "name"),
        length=_float(road_elem, "length"),
        junction=_str(road_elem, "junction", "-1"),
        plan_view=plan_view,
        elevation_profile=ElevationProfile(elevations=elevations),
        lateral_profile=LateralProfile(super_elevations=super_elevations),
        lanes=Lanes(lane_offsets=lane_offsets, lane_sections=lane_sections),
        objects=objects,
        signals=signals,
    )


def _parse_junction(elem: etree._Element) -> Junction:
    connections = []
    for conn_elem in _findall(elem, "connection"):
        lane_links = [
            JunctionLaneLink(
                from_lane=_int(ll, "from"),
                to_lane=_int(ll, "to"),
            )
            for ll in _findall(conn_elem, "laneLink")
        ]
        connections.append(
            JunctionConnection(
                id=_str(conn_elem, "id"),
                incoming_road=_str(conn_elem, "incomingRoad"),
                connecting_road=_str(conn_elem, "connectingRoad"),
                contact_point=_str(conn_elem, "contactPoint"),
                lane_links=lane_links,
            )
        )
    return Junction(
        id=_str(elem, "id"),
        name=_str(elem, "name"),
        connections=connections,
    )


def _safe_parser() -> etree.XMLParser:
    """Create an XML parser with external entity resolution disabled."""
    return etree.XMLParser(resolve_entities=False, no_network=True)


def parse_opendrive(filepath: str | Path) -> OpenDRIVE:
    """Parse an OpenDRIVE .xodr file into the dataclass model."""
    tree = etree.parse(str(filepath), _safe_parser())
    return _parse_root(tree.getroot())


def parse_opendrive_string(xml_string: str) -> OpenDRIVE:
    """Parse an OpenDRIVE XML string into the dataclass model."""
    root = etree.fromstring(xml_string.encode("utf-8"), _safe_parser())
    return _parse_root(root)


def _parse_root(root: etree._Element) -> OpenDRIVE:
    """Parse the root OpenDRIVE element."""
    # Header
    header_elem = _find(root, "header")
    geo_ref_elem = (
        _find(header_elem, "geoReference") if header_elem is not None else None
    )
    geo_ref = GeoReference(
        proj4=(
            geo_ref_elem.text.strip()
            if geo_ref_elem is not None and geo_ref_elem.text
            else ""
        ),
    )
    header = (
        Header(
            rev_major=_int(header_elem, "revMajor") if header_elem is not None else 0,
            rev_minor=_int(header_elem, "revMinor") if header_elem is not None else 0,
            name=_str(header_elem, "name") if header_elem is not None else "",
            version=_str(header_elem, "version") if header_elem is not None else "",
            date=_str(header_elem, "date") if header_elem is not None else "",
            north=_float(header_elem, "north") if header_elem is not None else 0.0,
            south=_float(header_elem, "south") if header_elem is not None else 0.0,
            east=_float(header_elem, "east") if header_elem is not None else 0.0,
            west=_float(header_elem, "west") if header_elem is not None else 0.0,
            geo_reference=geo_ref,
        )
        if header_elem is not None
        else Header(geo_reference=geo_ref)
    )

    # Roads
    roads = [_parse_road(r) for r in _findall(root, "road")]

    # Junctions
    junctions = [_parse_junction(j) for j in _findall(root, "junction")]

    return OpenDRIVE(header=header, roads=roads, junctions=junctions)
