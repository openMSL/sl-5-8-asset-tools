"""Asset file analyzer — extracts signals from source files for LLM context.

Parses .xodr (OpenDRIVE) and .xosc (OpenSCENARIO) files to extract
structured signals that help the LLM fill missing metadata fields.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def analyze_asset(asset_path: Path) -> dict[str, Any]:
    """Analyze an asset file and extract metadata signals."""
    suffix = asset_path.suffix.lower()
    if suffix == ".xodr":
        return _analyze_xodr(asset_path)
    elif suffix == ".xosc":
        return _analyze_xosc(asset_path)
    else:
        logger.warning("Unsupported file type: %s", suffix)
        return {}


def _analyze_xodr(path: Path) -> dict[str, Any]:
    """Extract metadata signals from an OpenDRIVE file."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    signals: dict[str, Any] = {"file_type": "OpenDRIVE", "file_name": path.stem}

    header = root.find("header")
    if header is not None:
        signals["header"] = {
            k: header.get(k, "") for k in ["name", "revMajor", "revMinor", "date"]
        }
        geo = header.find("geoReference")
        if geo is not None and geo.text:
            signals["geo_reference"] = geo.text.strip()

    roads = root.findall("road")
    signals["road_count"] = len(roads)

    road_types = set()
    lane_types = set()
    traffic_rules = set()
    has_signals = False
    has_objects = False

    for road in roads:
        rule = road.get("rule", "")
        if rule:
            traffic_rules.add(rule)

        for rtype in road.findall("type"):
            t = rtype.get("type", "")
            if t:
                road_types.add(t)

        for lane in road.findall(".//lane"):
            lt = lane.get("type", "")
            if lt:
                lane_types.add(lt)

        if road.findall(".//signal"):
            has_signals = True
        if road.findall(".//object"):
            has_objects = True

    signals["road_types"] = sorted(road_types)
    signals["lane_types"] = sorted(lane_types)
    signals["traffic_rules"] = sorted(traffic_rules)
    signals["has_signals"] = has_signals
    signals["has_objects"] = has_objects

    # Traffic direction inference
    if traffic_rules:
        if "RHT" in traffic_rules:
            signals["inferred_traffic_direction"] = "right-hand"
        elif "LHT" in traffic_rules:
            signals["inferred_traffic_direction"] = "left-hand"

    junctions = root.findall("junction")
    signals["junction_count"] = len(junctions)

    return signals


def _analyze_xosc(path: Path) -> dict[str, Any]:
    """Extract metadata signals from an OpenSCENARIO file."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    signals: dict[str, Any] = {"file_type": "OpenSCENARIO", "file_name": path.stem}

    header = root.find("FileHeader")
    if header is not None:
        signals["header"] = {
            k: header.get(k, "")
            for k in ["description", "author", "revMajor", "revMinor", "date"]
        }

    entities = root.findall(".//ScenarioObject") + root.findall(".//EntitySelection")
    signals["entity_count"] = len(entities)

    entity_types = set()
    for entity in root.findall(".//ScenarioObject"):
        for vehicle in entity.findall(".//Vehicle"):
            vtype = vehicle.get("vehicleCategory", vehicle.get("name", ""))
            if vtype:
                entity_types.add(vtype.lower())
        for pedestrian in entity.findall(".//Pedestrian"):
            entity_types.add("pedestrian")
        for misc in entity.findall(".//MiscObject"):
            entity_types.add("obstacle")

    signals["entity_types"] = sorted(entity_types)

    # Action analysis for scenario category inference
    action_types = set()
    for elem in root.iter():
        tag = elem.tag
        if tag.endswith("Action") and tag != "Action":
            action_types.add(tag)

    signals["action_types"] = sorted(action_types)

    # Maneuver names for category clues
    maneuver_names = []
    for m in root.findall(".//Maneuver"):
        name = m.get("name", "")
        if name:
            maneuver_names.append(name)
    signals["maneuver_names"] = maneuver_names

    # Weather
    weather = root.find(".//Weather")
    if weather is not None:
        signals["has_weather"] = True
        cloud = weather.get("fractionalCloudCover", "")
        if cloud:
            signals["cloud_cover"] = cloud

        fog = weather.find("Fog")
        if fog is not None:
            vis = fog.get("visualRange", "")
            signals["fog_visual_range"] = vis

        precip = weather.find("Precipitation")
        if precip is not None:
            ptype = precip.get("precipitationType", "")
            intensity = precip.get("intensity", "0")
            signals["precipitation"] = {"type": ptype, "intensity": intensity}

        sun = weather.find("Sun")
        if sun is not None:
            signals["sun"] = {
                k: sun.get(k, "") for k in ["azimuth", "elevation", "illuminance"]
            }

    # Time of day
    tod = root.find(".//TimeOfDay")
    if tod is not None:
        signals["time_of_day"] = tod.get("dateTime", "")

    # Positions for geo inference
    world_positions = []
    for wp in root.findall(".//WorldPosition"):
        x, y = wp.get("x", ""), wp.get("y", "")
        if x and y:
            world_positions.append({"x": float(x), "y": float(y)})
    if world_positions:
        signals["world_positions_sample"] = world_positions[:5]

    # Parameter declarations
    params = []
    for p in root.findall(".//ParameterDeclaration"):
        params.append({"name": p.get("name", ""), "value": p.get("value", "")})
    if params:
        signals["parameters"] = params[:10]

    # Controllers
    controllers = []
    for c in root.findall(".//Controller"):
        controllers.append(c.get("name", ""))
    if controllers:
        signals["controllers"] = controllers

    # Custom commands
    custom_cmds = []
    for cc in root.findall(".//CustomCommandAction"):
        custom_cmds.append(cc.get("type", ""))
    if custom_cmds:
        signals["custom_commands"] = custom_cmds

    return signals
