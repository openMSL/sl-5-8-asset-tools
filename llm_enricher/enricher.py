"""Rule-based metadata enrichment from asset analysis signals.

This module fills metadata fields deterministically from file content
without needing an LLM. Fields that can be directly extracted or
trivially inferred go through rules; the remaining gaps are marked
for optional LLM enrichment.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from maneuver/action keywords to scenario categories
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "cut-in": ["cutin", "cut_in", "cut-in", "cutout", "cut_out", "cut-out"],
    "emergency-braking": ["emergency", "braking", "deceleration", "aeb"],
    "following": ["following", "follow"],
    "free-driving": ["free_driving", "free-driving", "freedriving"],
    "intersection-crossing": ["intersection", "crossing", "junction"],
    "lane-change": ["lane_change", "lanechange", "lane-change"],
    "merging": ["merging", "merge"],
    "overtaking": ["overtaking", "overtake", "passing"],
    "parking": ["parking", "park"],
    "pedestrian-crossing": ["pedestrian_crossing", "pedestrian-crossing", "crosswalk"],
    "turning": ["turn", "left_turn", "right_turn"],
}

WEATHER_MAP: dict[str, str] = {
    "zeroOktas": "clear",
    "oneOktas": "clear",
    "twoOktas": "clear",
    "threeOktas": "clear",
    "fourOktas": "clear",
    "fiveOktas": "clear",
    "sixOktas": "clear",
    "sevenOktas": "clear",
    "eightOktas": "clear",
    "nineOktas": "clear",
}


def enrich_scenario(
    signals: dict[str, Any],
    existing: dict[str, Any],
    vocabulary: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing scenario metadata fields from analysis signals.

    Returns a dict of {field_name: enriched_value} for fields that
    could be determined. Values are None for fields that couldn't.
    """
    enriched: dict[str, Any] = {}
    confidence: dict[str, str] = {}

    # scenarioCategory
    category = _infer_scenario_category(signals)
    if category:
        enriched["scenarioCategory"] = category
        confidence["scenarioCategory"] = "high"

    # sourceType
    source_type = _infer_source_type(signals)
    if source_type:
        enriched["sourceType"] = source_type
        confidence["sourceType"] = "medium"

    # sourceDescription
    source_desc = _infer_source_description(signals)
    if source_desc:
        enriched["sourceDescription"] = source_desc
        confidence["sourceDescription"] = "medium"

    # aim
    aim = _infer_aim(signals)
    if aim:
        enriched["aim"] = aim
        confidence["aim"] = "medium"

    # country
    country = _infer_country(signals)
    if country:
        enriched["country"] = country
        confidence["country"] = "medium"

    # movementDescription
    movement = _infer_movement_description(signals)
    if movement:
        enriched["movementDescription"] = movement
        confidence["movementDescription"] = "medium"

    # criticalityFactors
    criticality = _infer_criticality_factors(signals, vocabulary)
    if criticality:
        enriched["criticalityFactors"] = criticality
        confidence["criticalityFactors"] = "medium"

    # weatherSummary (if not already filled)
    if "weatherSummary" not in existing:
        weather = _infer_weather(signals)
        if weather:
            enriched["weatherSummary"] = weather
            confidence["weatherSummary"] = "high"

    # controllers
    if signals.get("controllers"):
        enriched["controllers"] = ", ".join(signals["controllers"])
        confidence["controllers"] = "high"

    # customCommands
    if signals.get("custom_commands"):
        enriched["customCommands"] = ", ".join(signals["custom_commands"])
        confidence["customCommands"] = "high"

    # permanentTrafficObjects / temporaryTrafficObjects
    misc_count = len(
        [e for e in signals.get("entity_types", []) if e in ("obstacle", "miscobject")]
    )
    enriched["permanentTrafficObjects"] = misc_count
    confidence["permanentTrafficObjects"] = "medium"
    enriched["temporaryTrafficObjects"] = 0
    confidence["temporaryTrafficObjects"] = "low"

    # Validate enum values against SHACL vocabulary
    _validate_enums(enriched, confidence, vocabulary)

    return {"fields": enriched, "confidence": confidence}


def enrich_hdmap(
    signals: dict[str, Any],
    existing: dict[str, Any],
    vocabulary: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing hdmap metadata fields from analysis signals."""
    enriched: dict[str, Any] = {}
    confidence: dict[str, str] = {}

    # trafficDirection
    td = signals.get("inferred_traffic_direction")
    if td:
        enriched["trafficDirection"] = td
        confidence["trafficDirection"] = "high"

    # levelOfDetail
    lod = _infer_level_of_detail(signals)
    if lod:
        enriched["levelOfDetail"] = lod
        confidence["levelOfDetail"] = "medium"

    # usedDataSources
    source = _infer_hdmap_source(signals)
    if source:
        enriched["usedDataSources"] = source
        confidence["usedDataSources"] = "medium"

    # sourceDescription
    desc = _infer_hdmap_source_description(signals)
    if desc:
        enriched["sourceDescription"] = desc
        confidence["sourceDescription"] = "low"

    # Validate enum values against SHACL vocabulary
    _validate_enums(enriched, confidence, vocabulary)

    return {"fields": enriched, "confidence": confidence}


def _validate_enums(
    enriched: dict[str, Any],
    confidence: dict[str, str],
    vocabulary: dict[str, Any],
) -> None:
    """Remove enriched values that violate SHACL sh:in constraints."""
    enums = vocabulary.get("enums", {})
    for field_name in list(enriched):
        if field_name not in enums:
            continue
        valid_values = set(enums[field_name].get("values", []))
        value = enriched[field_name]
        if isinstance(value, list):
            filtered = [v for v in value if v in valid_values]
            if filtered:
                enriched[field_name] = filtered
            else:
                del enriched[field_name]
                confidence.pop(field_name, None)
        elif value not in valid_values:
            del enriched[field_name]
            confidence.pop(field_name, None)


def _infer_scenario_category(signals: dict[str, Any]) -> str | None:
    """Infer scenario category from file name, maneuvers, and actions."""
    search_text = " ".join(
        [
            signals.get("file_name", ""),
            " ".join(signals.get("maneuver_names", [])),
            signals.get("header", {}).get("description", ""),
        ]
    ).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in search_text for kw in keywords):
            return category

    # Action-based inference
    actions = set(a.lower() for a in signals.get("action_types", []))
    if "lanechangeaction" in actions:
        return "lane-change"
    if "followtrajectoryaction" in actions:
        return "following"

    return None


def _infer_source_type(signals: dict[str, Any]) -> str | None:
    """Infer data source type from author and file metadata."""
    author = signals.get("header", {}).get("author", "").lower()
    desc = signals.get("header", {}).get("description", "").lower()
    fname = signals.get("file_name", "").lower()

    if "vufo" in fname or "verkehrsunfall" in author:
        return "Accident Database"
    if "wmg" in author or "verification and validation" in author:
        return "Analytical Hazard Based Approach"
    if "scenariotoolkit" in author or "auto-generated" in desc:
        return "Synthetic Generation"
    if any(kw in author for kw in ["safetypool", "safety pool", "safety-pool"]):
        return "Accident Database"
    if "manual" in desc:
        return "Manual Authoring"

    # UUID-style names often indicate Safety Pool (accident database)
    if re.match(r"^[0-9a-fA-F]{8}-", fname):
        return "Accident Database"

    return None


def _infer_source_description(signals: dict[str, Any]) -> str | None:
    """Build a source description from available signals."""
    author = signals.get("header", {}).get("author", "")
    desc = signals.get("header", {}).get("description", "")

    parts = []
    if author:
        parts.append(f"Created by {author}")
    if desc:
        parts.append(desc)

    return ". ".join(parts) if parts else None


def _infer_aim(signals: dict[str, Any]) -> str | None:
    """Infer scenario aim from description and file name."""
    desc = signals.get("header", {}).get("description", "")
    fname = signals.get("file_name", "")

    if desc and desc != fname:
        return desc

    # Try to make file name readable
    readable = fname.replace("_", " ").replace("-", " ")
    if readable and len(readable) > 3:
        return f"Simulation of {readable} scenario"

    return None


def _infer_country(signals: dict[str, Any]) -> str | None:
    """Infer country from various signals."""
    author = signals.get("header", {}).get("author", "").lower()

    # German institutions
    if any(kw in author for kw in ["tu dresden", "vufo", "ika", "rwth", "vector"]):
        return "DE"
    # UK institutions
    if any(kw in author for kw in ["wmg", "warwick", "coventry"]):
        return "GB"

    return None


def _infer_movement_description(signals: dict[str, Any]) -> str | None:
    """Summarize movement types from action analysis."""
    actions = signals.get("action_types", [])
    if not actions:
        return None

    movement_map = {
        "SpeedAction": "speed changes",
        "LaneChangeAction": "lane changes",
        "TeleportAction": "position initialization",
        "FollowTrajectoryAction": "trajectory following",
        "AcquirePositionAction": "position acquisition",
        "LongitudinalAction": "longitudinal motion",
        "LateralAction": "lateral motion",
        "RoutingAction": "route following",
    }

    movements = []
    for action in actions:
        clean = action.replace("Action", "").replace("action", "")
        if action in movement_map:
            movements.append(movement_map[action])
        elif clean:
            readable = re.sub(r"(?<!^)(?=[A-Z])", " ", clean).lower()
            movements.append(readable)

    if movements:
        unique = list(dict.fromkeys(movements))
        return ", ".join(unique[:5])

    return None


def _infer_criticality_factors(
    signals: dict[str, Any], vocabulary: dict[str, Any]
) -> list[str] | None:
    """Infer criticality factors from scenario content."""
    valid_values = set(
        vocabulary.get("enums", {}).get("criticalityFactors", {}).get("values", [])
    )
    if not valid_values:
        valid_values = {
            "VRU_interaction",
            "adverse_weather",
            "high_relative_speed",
            "infrastructure_violation",
            "near_miss",
            "occlusion",
        }

    factors = []

    entities = set(signals.get("entity_types", []))
    vru_types = {"pedestrian", "bicycle", "wheelchair"}
    if entities & vru_types:
        factors.append("VRU_interaction")

    if signals.get("precipitation") or signals.get("fog_visual_range"):
        fog_range = signals.get("fog_visual_range", "")
        try:
            if fog_range and float(fog_range) < 1000:
                factors.append("adverse_weather")
        except (ValueError, TypeError):
            pass
        precip = signals.get("precipitation", {})
        try:
            if (
                precip.get("intensity", "0") != "0"
                and float(precip.get("intensity", "0")) > 0
            ):
                factors.append("adverse_weather")
        except (ValueError, TypeError):
            pass

    # High relative speed from scenario name/description clues
    fname = signals.get("file_name", "").lower()
    if any(kw in fname for kw in ["emergency", "braking", "deceleration", "aeb"]):
        factors.append("high_relative_speed")

    return [f for f in factors if f in valid_values] or None


def _infer_weather(signals: dict[str, Any]) -> str | None:
    """Infer weather summary from weather signals."""
    if not signals.get("has_weather"):
        return None

    precip = signals.get("precipitation", {})
    if precip.get("type") == "rain":
        try:
            if float(precip.get("intensity", "0")) > 0:
                return "rain"
        except (ValueError, TypeError):
            pass
    if precip.get("type") == "snow":
        try:
            if float(precip.get("intensity", "0")) > 0:
                return "snow"
        except (ValueError, TypeError):
            pass

    fog_range = signals.get("fog_visual_range", "")
    if fog_range:
        try:
            if float(fog_range) < 500:
                return "fog"
        except (ValueError, TypeError):
            pass

    sun = signals.get("sun", {})
    try:
        if sun.get("elevation") and float(sun.get("elevation", "0")) < 0:
            return "night"
    except (ValueError, TypeError):
        pass

    cloud = signals.get("cloud_cover", "")
    if cloud in WEATHER_MAP:
        return WEATHER_MAP[cloud]

    return "clear"


def _infer_level_of_detail(signals: dict[str, Any]) -> list[str] | None:
    """Infer HD map level of detail (object types present).

    SHACL constrains this to e_objectType values for OpenDRIVE v1.5+.
    """
    # levelOfDetail in the ontology means "which object types are present"
    # We can't reliably determine this without deep object analysis
    return None


def _infer_hdmap_source(signals: dict[str, Any]) -> str | None:
    """Infer HD map data source."""
    header = signals.get("header", {})
    name = header.get("name", "").lower()

    if "ncap" in name or "straight" in name:
        return "Synthetic Generation"
    if signals.get("geo_reference"):
        return "Survey / Measurement"

    return "Synthetic Generation"


def _infer_hdmap_source_description(signals: dict[str, Any]) -> str | None:
    """Build HD map source description."""
    header = signals.get("header", {})
    name = header.get("name", "")
    if name:
        return f"HD map: {name}"
    return None
