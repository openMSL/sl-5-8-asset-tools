"""Signal dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signal:
    """A traffic signal or sign."""

    id: str = ""
    name: str = ""
    type: str = ""
    subtype: str = ""
    s: float = 0.0
    t: float = 0.0
    z_offset: float = 0.0
    hdg: float = 0.0
    orientation: str = ""
    value: float = 0.0
    dynamic: str = ""
    country: str = ""
    # Populated during generation
    geometries: list = field(default_factory=list)
    computed_heading: float = 0.0
