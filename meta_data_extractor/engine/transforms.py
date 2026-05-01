"""Transform registry for complex extraction logic.

Transforms are named functions that receive raw data from the decoded XML dict
and return processed values. They handle logic too complex for a simple path
expression (e.g., weather classification, elevation polynomial evaluation).

Register transforms using the ``@register`` decorator::

    from meta_data_extractor.engine.transforms import register

    @register("derive_weather_summary")
    def derive_weather_summary(data: Any, **kwargs) -> str:
        ...
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Global transform registry
_REGISTRY: dict[str, Callable] = {}


def register(name: str) -> Callable:
    """Decorator to register a transform function by name."""

    def wrapper(func: Callable) -> Callable:
        if name in _REGISTRY:
            logger.warning("Overwriting transform '%s'", name)
        _REGISTRY[name] = func
        return func

    return wrapper


def get_transform(name: str) -> Callable:
    """Retrieve a registered transform by name."""
    if name not in _REGISTRY:
        raise KeyError(
            f"Transform '{name}' not registered. Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]


def list_transforms() -> list[str]:
    """List all registered transform names."""
    return sorted(_REGISTRY.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Built-in transforms
# ═══════════════════════════════════════════════════════════════════════════════


@register("count")
def count_elements(data: Any, **kwargs) -> int:
    """Count the number of elements in a list or dict."""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return 1
    return 0


@register("count_filtered")
def count_filtered(data: Any, **kwargs) -> int:
    """Count elements matching a filter condition.

    Args (via kwargs):
        attribute: The attribute key to check
        value: The value to match against
    """
    attribute = kwargs.get("attribute", "")
    value = kwargs.get("value", "")
    if not isinstance(data, list):
        data = [data] if data else []
    return sum(
        1
        for item in data
        if isinstance(item, dict) and item.get(f"@{attribute}") == value
    )


@register("collect_unique")
def collect_unique(data: Any, **kwargs) -> str:
    """Collect unique values from a list, comma-joined."""
    if isinstance(data, list):
        unique = sorted(set(str(v) for v in data if v is not None))
    elif data is not None:
        unique = [str(data)]
    else:
        unique = []
    separator = kwargs.get("separator", ", ")
    return separator.join(unique)


@register("collect_element_names")
def collect_element_names(data: Any, **kwargs) -> str:
    """Collect all unique descendant element/tag names used in the document.

    Operates on the raw ElementTree root passed via kwargs['element_tree'].
    Excludes the root element itself (matching findall('.//')  behavior).
    """
    tree = kwargs.get("element_tree")
    if tree is None:
        return ""
    # Use findall('.//' ) to get descendants only (excludes root)
    names = sorted({elem.tag for elem in tree.findall(".//")})
    return ", ".join(names)


@register("sum_values")
def sum_values(data: Any, **kwargs) -> float:
    """Sum numeric values from a list."""
    if not isinstance(data, list):
        data = [data] if data else []
    return sum(float(v) for v in data if v is not None)


@register("concat_version")
def concat_version(data: Any, **kwargs) -> str:
    """Concatenate major.minor version from a header dict.

    Handles both a single dict and a list with one dict (from path resolution).
    """
    if isinstance(data, list):
        data = data[0] if data else {}
    if isinstance(data, dict):
        major = data.get("@revMajor", "1")
        minor = data.get("@revMinor", "0")
        return f"{major}.{minor}"
    return str(data) if data else ""


@register("derive_weather_summary")
def derive_weather_summary(data: Any, **kwargs) -> str:
    """Derive a coarse weatherSummary from Environment/Weather elements.

    Maps OpenSCENARIO precipitation/fog/wind/sun to the ontology enum:
    clear | rain | snow | fog | icy_conditions | night | windy | mixed | not_specified
    """
    if not isinstance(data, list):
        data = [data] if data else []

    indicators: set[str] = set()

    for weather in data:
        if not isinstance(weather, dict):
            continue

        # Check precipitation
        precip = weather.get("Precipitation")
        if isinstance(precip, dict):
            ptype = str(precip.get("@precipitationType", "")).lower()
            intensity = float(precip.get("@intensity", 0) or 0)
            if ptype == "rain" and intensity > 0:
                indicators.add("rain")
            elif ptype == "snow" and intensity > 0:
                indicators.add("snow")

        # Check fog
        fog = weather.get("Fog")
        if isinstance(fog, dict):
            vis_range = float(fog.get("@visualRange", 10000) or 10000)
            if vis_range < 1000:
                indicators.add("fog")

        # Check wind
        wind = weather.get("Wind")
        if isinstance(wind, dict):
            speed = float(wind.get("@speed", 0) or 0)
            if speed > 10:
                indicators.add("windy")

        # Check sun elevation (night detection)
        sun = weather.get("Sun")
        if isinstance(sun, dict):
            elevation = float(sun.get("@elevation", 0.5) or 0.5)
            if elevation < 0:
                indicators.add("night")

    if not indicators:
        return "clear"
    if len(indicators) == 1:
        return indicators.pop()
    return "mixed"


@register("derive_abstraction_level")
def derive_abstraction_level(data: Any, **kwargs) -> str:
    """Derive scenario abstraction level from document structure.

    - If ParameterValueDistributionDefinition present → "Logical"
    - If ScenarioDefinition with parameter declarations → "Logical"
    - Otherwise → "Concrete"
    """
    if not isinstance(data, dict):
        return "Concrete"

    if data.get("ParameterValueDistribution") is not None:
        return "Logical"

    storyboard = data.get("Storyboard")
    if storyboard is None:
        # Might be a catalog or parametric definition
        if data.get("Catalog") is not None:
            return "Functional"
        return "Concrete"

    # Check for parameter declarations (indicates parametric/logical)
    param_decls = data.get("ParameterDeclarations")
    if isinstance(param_decls, dict) and param_decls.get("ParameterDeclaration"):
        return "Logical"

    return "Concrete"


@register("sum_div_1000")
def sum_div_1000(data: Any, **kwargs) -> float:
    """Sum numeric values and divide by 1000 (e.g., meters → kilometers)."""
    if not isinstance(data, list):
        data = [data] if data else []
    total = sum(float(v) for v in data if v is not None)
    return total / 1000


@register("collect_custom_commands")
def collect_custom_commands(data: Any, **kwargs) -> str:
    """Extract unique UserDefinedAction @type values."""
    tree = kwargs.get("element_tree")
    if tree is None:
        return ""
    user_defined = tree.findall(".//{*}UserDefinedAction") or tree.findall(
        ".//UserDefinedAction"
    )
    types = sorted({el.get("type", "") for el in user_defined if el.get("type")})
    return ", ".join(types) if types else ""


@register("collect_controllers")
def collect_controllers(data: Any, **kwargs) -> str:
    """Extract controller type:name pairs from scenario objects."""
    if not isinstance(data, list):
        data = [data] if data else []
    controllers = set()
    for ctrl in data:
        if not isinstance(ctrl, dict):
            continue
        ctrl_type = ctrl.get("@controllerType", "")
        name = ctrl.get("@name", "")
        if ctrl_type:
            controllers.add(f"{ctrl_type}: {name}")
        elif name:
            controllers.add(name)
    return ", ".join(sorted(controllers)) if controllers else ""


@register("extract_country_signs")
def extract_country_signs(data: Any, **kwargs) -> str:
    """Extract country-specific traffic signs from the associated map.

    Operates on the raw lxml tree since this requires searching the map file.
    """
    tree = kwargs.get("element_tree")
    if tree is None:
        return ""
    signals = tree.findall(".//{*}signal") or tree.findall(".//signal")
    signs = sorted(
        {
            f"{sig.get('country')}:{sig.get('type')}"
            for sig in signals
            if sig.get("country") and sig.get("country") != "OpenDRIVE"
        }
    )
    return ", ".join(signs) if signs else ""


@register("elevation_range")
def elevation_range(data: Any, **kwargs) -> str:
    """Compute elevation range from OpenDRIVE cubic polynomial coefficients.

    Each elevation element has a, b, c, d, s attributes defining a cubic:
        z(ds) = a + b*ds + c*ds² + d*ds³
    where ds is the distance from the start of the elevation segment.
    """
    if not isinstance(data, list):
        data = [data] if data else []
    if not data:
        return 0.0

    global_min = float("inf")
    global_max = float("-inf")

    # Sort by s-coordinate
    sorted_elems = sorted(
        (e for e in data if isinstance(e, dict)),
        key=lambda e: float(e.get("@s", 0) or 0),
    )

    for i, elem in enumerate(sorted_elems):
        a = float(elem.get("@a", 0) or 0)
        b = float(elem.get("@b", 0) or 0)
        c = float(elem.get("@c", 0) or 0)
        d = float(elem.get("@d", 0) or 0)
        s_start = float(elem.get("@s", 0) or 0)

        # Determine segment length (to next segment or end of road)
        if i + 1 < len(sorted_elems):
            s_end = float(sorted_elems[i + 1].get("@s", s_start) or s_start)
        else:
            # Approximate: use road length from kwargs or a reasonable default
            s_end = s_start + float(kwargs.get("segment_length", 100))

        ds_max = s_end - s_start
        if ds_max <= 0:
            continue

        # Evaluate at endpoints and critical points
        def poly(ds: float) -> float:
            return a + b * ds + c * ds**2 + d * ds**3

        values = [poly(0), poly(ds_max)]

        # Find critical points (derivative = 0): b + 2c*ds + 3d*ds² = 0
        if d != 0:
            disc = (2 * c) ** 2 - 4 * (3 * d) * b
            if disc >= 0:
                sqrt_disc = disc**0.5
                for ds_crit in [
                    (-2 * c + sqrt_disc) / (6 * d),
                    (-2 * c - sqrt_disc) / (6 * d),
                ]:
                    if 0 < ds_crit < ds_max:
                        values.append(poly(ds_crit))
        elif c != 0:
            ds_crit = -b / (2 * c)
            if 0 < ds_crit < ds_max:
                values.append(poly(ds_crit))

        global_min = min(global_min, *values)
        global_max = max(global_max, *values)

    if global_min == float("inf"):
        return ""
    return f"{global_min:.2f} - {global_max:.2f}"
