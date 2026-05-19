"""Tests for the schema-driven extraction engine.

Tests the core components: decoder, engine, mapping, transforms.
"""

import pytest

from meta_data_extractor.engine.engine import ExtractionEngine, _split_path
from meta_data_extractor.engine.mapping import MappingConfig
from meta_data_extractor.engine.transforms import (
    get_transform,
    list_transforms,
    count_elements,
    collect_unique,
    concat_version,
    derive_weather_summary,
    derive_abstraction_level,
    sum_div_1000,
    elevation_range,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Path splitting
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathSplitting:
    def test_simple_path(self):
        assert _split_path("FileHeader.@revMajor") == ["FileHeader", "@revMajor"]

    def test_array_wildcard(self):
        assert _split_path("Entities.ScenarioObject[*].Vehicle") == [
            "Entities",
            "ScenarioObject[*]",
            "Vehicle",
        ]

    def test_deep_path(self):
        parts = _split_path(
            "Storyboard.Init.Actions.GlobalAction[*].EnvironmentAction.Environment.Weather.Sun.@azimuth"
        )
        assert parts[0] == "Storyboard"
        assert parts[3] == "GlobalAction[*]"
        assert parts[-1] == "@azimuth"

    def test_single_key(self):
        assert _split_path("FileHeader") == ["FileHeader"]


# ═══════════════════════════════════════════════════════════════════════════════
# Engine path resolution
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnginePathResolution:
    def setup_method(self):
        self.engine = ExtractionEngine()

    def test_simple_attribute(self):
        data = {"FileHeader": {"@revMajor": "1", "@revMinor": "3"}}
        values = self.engine._resolve_path(data, "FileHeader.@revMajor")
        assert values == ["1"]

    def test_nested_access(self):
        data = {"A": {"B": {"C": "hello"}}}
        assert self.engine._resolve_path(data, "A.B.C") == ["hello"]

    def test_missing_key_returns_empty(self):
        data = {"A": {"B": 1}}
        assert self.engine._resolve_path(data, "A.X.Y") == []

    def test_array_wildcard_single_item(self):
        data = {"Entities": {"ScenarioObject": {"@name": "ego"}}}
        values = self.engine._resolve_path(data, "Entities.ScenarioObject[*].@name")
        assert values == ["ego"]

    def test_array_wildcard_multiple_items(self):
        data = {
            "Entities": {
                "ScenarioObject": [
                    {"@name": "ego", "Vehicle": {"@vehicleCategory": "car"}},
                    {"@name": "other", "Vehicle": {"@vehicleCategory": "truck"}},
                ]
            }
        }
        values = self.engine._resolve_path(
            data, "Entities.ScenarioObject[*].Vehicle.@vehicleCategory"
        )
        assert values == ["car", "truck"]

    def test_deep_nested_with_wildcard(self):
        data = {
            "Storyboard": {
                "Init": {
                    "Actions": {
                        "GlobalAction": [
                            {
                                "EnvironmentAction": {
                                    "Environment": {
                                        "Weather": {"Sun": {"@azimuth": 0.5}}
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        values = self.engine._resolve_path(
            data,
            "Storyboard.Init.Actions.GlobalAction[*].EnvironmentAction.Environment.Weather.Sun.@azimuth",
        )
        assert values == [0.5]


# ═══════════════════════════════════════════════════════════════════════════════
# Collectors
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollectors:
    def setup_method(self):
        self.engine = ExtractionEngine()

    def test_first(self):
        assert self.engine._collect(["a", "b", "c"], "first") == "a"

    def test_all(self):
        assert self.engine._collect(["a", "b", "c"], "all") == "a, b, c"

    def test_all_unique(self):
        assert self.engine._collect(["b", "a", "b", "c"], "all_unique") == "a, b, c"

    def test_count(self):
        assert self.engine._collect([1, 2, 3], "count") == 3

    def test_sum(self):
        assert self.engine._collect([1.5, 2.5, 3.0], "sum") == 7.0

    def test_min_max(self):
        assert self.engine._collect([3, 1, 2], "min") == 1
        assert self.engine._collect([3, 1, 2], "max") == 3

    def test_empty_returns_none(self):
        assert self.engine._collect([], "first") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Type casting
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeCasting:
    def setup_method(self):
        self.engine = ExtractionEngine()

    def test_string(self):
        assert self.engine._cast(42, "string") == "42"

    def test_float(self):
        assert self.engine._cast("3.14", "float") == 3.14

    def test_int(self):
        assert self.engine._cast("7.9", "int") == 7

    def test_bool_true(self):
        assert self.engine._cast("true", "bool") is True

    def test_bool_false(self):
        assert self.engine._cast("false", "bool") is False

    def test_none_passthrough(self):
        assert self.engine._cast(None, "float") is None

    def test_raw(self):
        val = {"a": 1}
        assert self.engine._cast(val, "raw") is val


# ═══════════════════════════════════════════════════════════════════════════════
# Filters
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilters:
    def setup_method(self):
        self.engine = ExtractionEngine()

    def test_equals_filter(self):
        data = [
            {"@subtype": "trafficLight"},
            {"@subtype": "trafficSign"},
            {"@subtype": "trafficLight"},
        ]
        result = self.engine._apply_filter(
            data, {"attribute": "subtype", "equals": "trafficLight"}
        )
        assert len(result) == 2

    def test_not_equals_filter(self):
        data = [
            {"@country": "OpenDRIVE", "@type": "none"},
            {"@country": "DE", "@type": "274"},
            {"@country": "DE", "@type": "276"},
        ]
        result = self.engine._apply_filter(
            data, {"attribute": "country", "not_equals": "OpenDRIVE"}
        )
        assert len(result) == 2
        assert all(r["@country"] == "DE" for r in result)


# ═══════════════════════════════════════════════════════════════════════════════
# Transforms
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransforms:
    def test_registry_has_builtins(self):
        names = list_transforms()
        assert "count" in names
        assert "derive_weather_summary" in names
        assert "elevation_range" in names

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="not registered"):
            get_transform("nonexistent_transform")

    def test_count_elements(self):
        assert count_elements([1, 2, 3]) == 3
        assert count_elements({"a": 1}) == 1
        assert count_elements(None) == 0

    def test_collect_unique(self):
        assert collect_unique(["b", "a", "b"]) == "a, b"
        assert collect_unique("single") == "single"

    def test_concat_version(self):
        assert concat_version({"@revMajor": "1", "@revMinor": "3"}) == "1.3"
        assert concat_version({"@revMajor": "1"}) == "1.0"

    def test_weather_clear(self):
        weather = [
            {
                "Precipitation": {"@precipitationType": "dry", "@intensity": 0},
                "Sun": {"@elevation": 1.0},
            }
        ]
        assert derive_weather_summary(weather) == "clear"

    def test_weather_rain(self):
        weather = [
            {
                "Precipitation": {"@precipitationType": "rain", "@intensity": 0.5},
                "Sun": {"@elevation": 1.0},
            }
        ]
        assert derive_weather_summary(weather) == "rain"

    def test_weather_night_fog_mixed(self):
        weather = [
            {
                "Fog": {"@visualRange": 200},
                "Sun": {"@elevation": -5.0},
            }
        ]
        assert derive_weather_summary(weather) == "mixed"

    def test_weather_empty(self):
        assert derive_weather_summary([]) == "clear"

    def test_abstraction_concrete(self):
        data = {"Storyboard": {"Init": {}}}
        assert derive_abstraction_level(data) == "Concrete"

    def test_abstraction_logical(self):
        data = {
            "Storyboard": {"Init": {}},
            "ParameterDeclarations": {"ParameterDeclaration": [{"@name": "speed"}]},
        }
        assert derive_abstraction_level(data) == "Logical"

    def test_sum_div_1000(self):
        assert sum_div_1000([500, 1500, 3000]) == 5.0
        assert sum_div_1000([]) == 0.0

    def test_elevation_range_flat(self):
        data = [{"@s": 0, "@a": 5.0, "@b": 0, "@c": 0, "@d": 0}]
        result = elevation_range(data, segment_length=100)
        assert result == 0.0

    def test_elevation_range_linear(self):
        # Linear rise: z = 0 + 0.1*ds → at ds=100: z=10
        data = [{"@s": 0, "@a": 0.0, "@b": 0.1, "@c": 0, "@d": 0}]
        result = elevation_range(data, segment_length=100)
        assert result == 10.0


# ═══════════════════════════════════════════════════════════════════════════════
# Mapping config
# ═══════════════════════════════════════════════════════════════════════════════


class TestMappingConfig:
    def test_from_dict_simple(self):
        config = MappingConfig.from_dict(
            {
                "schema_format": "openscenario",
                "ontology_prefix": "scenario",
                "mappings": {
                    "scenario:formatType": {"value": "ASAM OpenSCENARIO XML"},
                    "scenario:version": {
                        "path": "FileHeader",
                        "transform": "concat_version",
                    },
                },
            }
        )
        assert config.schema_format == "openscenario"
        assert len(config.rules) == 2
        assert config.rules[0].property == "scenario:formatType"
        assert config.rules[0].value == "ASAM OpenSCENARIO XML"
        assert config.rules[1].transform == "concat_version"

    def test_from_dict_shorthand(self):
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "scenario:description": "FileHeader.@description",
                }
            }
        )
        assert config.rules[0].path == "FileHeader.@description"


# ═══════════════════════════════════════════════════════════════════════════════
# Full engine integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestEngineIntegration:
    def test_constant_value(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {"mappings": {"scenario:formatType": {"value": "ASAM OpenSCENARIO XML"}}}
        )
        result = engine.extract({}, config)
        assert result["scenario:formatType"] == "ASAM OpenSCENARIO XML"

    def test_path_with_collector(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "scenario:entityTypes": {
                        "path": "Entities.ScenarioObject[*].Vehicle.@vehicleCategory",
                        "collector": "all_unique",
                        "type": "string",
                    }
                }
            }
        )
        data = {
            "Entities": {
                "ScenarioObject": [
                    {"Vehicle": {"@vehicleCategory": "car"}},
                    {"Vehicle": {"@vehicleCategory": "truck"}},
                    {"Vehicle": {"@vehicleCategory": "car"}},
                ]
            }
        }
        result = engine.extract(data, config)
        assert result["scenario:entityTypes"] == "car, truck"

    def test_transform_with_path(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "scenario:version": {
                        "path": "FileHeader",
                        "transform": "concat_version",
                    }
                }
            }
        )
        data = {"FileHeader": {"@revMajor": "1", "@revMinor": "2"}}
        result = engine.extract(data, config)
        assert result["scenario:version"] == "1.2"

    def test_none_values_excluded(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "scenario:sunAzimuth": {
                        "path": "Storyboard.Weather.Sun.@azimuth",
                        "collector": "first",
                    }
                }
            }
        )
        # Path doesn't match → should not appear in result
        result = engine.extract({"Storyboard": {}}, config)
        assert "scenario:sunAzimuth" not in result

    def test_also_search_merges(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "hdmap:laneTypes": {
                        "path": "road[*].lanes.right.lane[*].@type",
                        "also_search": ["road[*].lanes.left.lane[*].@type"],
                        "collector": "all_unique",
                    }
                }
            }
        )
        data = {
            "road": [
                {
                    "lanes": {
                        "right": {
                            "lane": [{"@type": "driving"}, {"@type": "shoulder"}]
                        },
                        "left": {"lane": [{"@type": "driving"}, {"@type": "sidewalk"}]},
                    }
                }
            ]
        }
        result = engine.extract(data, config)
        assert "driving" in result["hdmap:laneTypes"]
        assert "shoulder" in result["hdmap:laneTypes"]
        assert "sidewalk" in result["hdmap:laneTypes"]

    def test_filter_with_count(self):
        engine = ExtractionEngine()
        config = MappingConfig.from_dict(
            {
                "mappings": {
                    "hdmap:numberTrafficLights": {
                        "path": "road[*].objects.object[*]",
                        "filter": {"attribute": "subtype", "equals": "trafficLight"},
                        "collector": "count",
                        "type": "int",
                    }
                }
            }
        )
        data = {
            "road": [
                {
                    "objects": {
                        "object": [
                            {"@subtype": "trafficLight"},
                            {"@subtype": "trafficSign"},
                            {"@subtype": "trafficLight"},
                        ]
                    }
                }
            ]
        }
        result = engine.extract(data, config)
        assert result["hdmap:numberTrafficLights"] == 2
