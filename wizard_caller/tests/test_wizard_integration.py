"""Integration tests for wizard_caller against the live TypeScript API.

These tests require the sd-creation-wizard API to be running on localhost:3007.
Skip automatically if the API is not available.

Run with:
    pytest wizard_caller/tests/test_wizard_integration.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wizard_caller.api_client import convert_and_prefill, is_api_available

API_URL = "http://localhost:3007"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(autouse=True)
def _require_api():
    """Skip all tests if the wizard API is not running."""
    if not is_api_available(API_URL):
        pytest.skip("Wizard API not running at " + API_URL)


class TestConvertFileIntegration:
    """Test /convertFile endpoint with real SHACL from the pipeline."""

    def _find_shacl_files(self):
        """Find all temp/*.ttl SHACL files in examples."""
        return sorted(EXAMPLES.rglob("temp/*.ttl"))

    def test_hdmap_shacl_converts_successfully(self):
        ttl_files = list(EXAMPLES.rglob("temp/hdmap.ttl"))
        assert len(ttl_files) > 0, "No hdmap.ttl found in examples"

        shacl_path = ttl_files[0]
        # Use a minimal JSON-LD for prefill
        jsonld_path = shacl_path.parent / "hdmap.json"

        result = convert_and_prefill(API_URL, shacl_path, jsonld_path)
        model = result["shaclModel"]

        assert "shapes" in model
        assert "prefixList" in model
        assert len(model["shapes"]) > 0
        assert len(model["prefixList"]) > 0

        # Validate shape structure
        for shape in model["shapes"]:
            assert "schema" in shape
            assert "constraints" in shape
            assert isinstance(shape["constraints"], list)

    def test_scenario_shacl_converts_successfully(self):
        ttl_files = list(EXAMPLES.rglob("temp/scenario.ttl"))
        if not ttl_files:
            pytest.skip("No scenario.ttl found in examples")

        shacl_path = ttl_files[0]
        jsonld_path = shacl_path.parent / "scenario.json"

        result = convert_and_prefill(API_URL, shacl_path, jsonld_path)
        model = result["shaclModel"]

        assert len(model["shapes"]) > 0
        assert len(model["prefixList"]) > 0

    def test_all_shacl_files_parse_without_error(self):
        """Every SHACL .ttl in examples should convert without HTTP error."""
        import requests

        ttl_files = list(EXAMPLES.rglob("temp/*.ttl"))
        assert len(ttl_files) > 0

        failures = []
        for ttl_path in ttl_files:
            url = f"{API_URL}/convertFile"
            with open(ttl_path, "rb") as f:
                resp = requests.post(
                    url, files={"file": (ttl_path.name, f, "text/turtle")}, timeout=30
                )
            if resp.status_code != 200:
                failures.append(f"{ttl_path.name}: HTTP {resp.status_code}")

        assert failures == [], f"Failed to convert: {failures}"

    def test_shape_constraints_have_expected_fields(self):
        """Validate that shape constraints contain proper structure."""
        ttl_files = list(EXAMPLES.rglob("temp/hdmap.ttl"))
        assert len(ttl_files) > 0

        shacl_path = ttl_files[0]
        jsonld_path = shacl_path.parent / "hdmap.json"

        result = convert_and_prefill(API_URL, shacl_path, jsonld_path)
        shapes = result["shaclModel"]["shapes"]

        for shape in shapes:
            for constraint in shape["constraints"]:
                # Every constraint must have at minimum these
                assert "datatype" in constraint or "or" in constraint, (
                    f"Constraint in {shape['schema']} missing datatype/or"
                )


class TestConvertAndPrefillIntegration:
    """Test /convertAndPrefillFile with real pipeline outputs."""

    def test_returns_both_model_and_matched(self):
        ttl_files = list(EXAMPLES.rglob("temp/hdmap.ttl"))
        assert len(ttl_files) > 0

        shacl_path = ttl_files[0]
        jsonld_path = shacl_path.parent / "hdmap.json"

        result = convert_and_prefill(API_URL, shacl_path, jsonld_path)

        assert "shaclModel" in result
        assert "matchedSubjects" in result
        assert isinstance(result["matchedSubjects"], dict)

    def test_matched_subjects_finds_expanded_uris(self):
        """If JSON-LD contains full URIs, they should match SHACL paths."""
        # Create a JSON-LD with expanded URIs that match hdmap SHACL paths
        ttl_files = list(EXAMPLES.rglob("temp/hdmap.ttl"))
        if not ttl_files:
            pytest.skip("No hdmap.ttl found")

        shacl_path = ttl_files[0]

        # First, get the model to find valid paths
        import requests

        with open(shacl_path, "rb") as f:
            resp = requests.post(
                f"{API_URL}/convertFile",
                files={"file": (shacl_path.name, f, "text/turtle")},
                timeout=30,
            )
        model = resp.json()

        # Find a constraint with a path
        test_path = None
        for shape in model["shapes"]:
            for c in shape["constraints"]:
                if "path" in c and c["path"]:
                    path_info = c["path"]
                    test_path = path_info
                    break
            if test_path:
                break

        if not test_path:
            pytest.skip("No constraint with path found")

        # Find the prefix URL from prefixList
        prefix_url = None
        for p in model["prefixList"]:
            if p["alias"] == test_path["prefix"]:
                prefix_url = p["url"]
                break

        if not prefix_url:
            pytest.skip(f"Prefix {test_path['prefix']} not in prefixList")

        full_uri = prefix_url + test_path["value"]

        # Create JSON-LD with this full URI
        import tempfile

        jsonld_data = {full_uri: "test-value-123"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(jsonld_data, f)
            tmp_json = Path(f.name)

        try:
            result = convert_and_prefill(API_URL, shacl_path, tmp_json)
            matched = result["matchedSubjects"]
            assert full_uri in matched, (
                f"Expected {full_uri} in matchedSubjects, got: {list(matched.keys())[:5]}"
            )
            assert matched[full_uri] == "test-value-123"
        finally:
            tmp_json.unlink()
