"""Tests for the wizard API client and API-backed enrichment."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wizard.api_client import (
    WizardAPIError,
    convert_and_prefill,
    is_api_available,
)


# ── API client tests ─────────────────────────────────────────────────


class TestIsApiAvailable:
    @patch("wizard.api_client.requests.get")
    def test_returns_true_when_reachable(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        assert is_api_available("http://localhost:8080") is True

    @patch("wizard.api_client.requests.get")
    def test_returns_false_on_connection_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.ConnectionError("refused")
        assert is_api_available("http://localhost:8080") is False

    @patch("wizard.api_client.requests.get")
    def test_returns_false_on_timeout(self, mock_get):
        import requests

        mock_get.side_effect = requests.Timeout("timed out")
        assert is_api_available("http://localhost:8080") is False


class TestConvertAndPrefill:
    @patch("wizard.api_client.requests.post")
    def test_success(self, mock_post, tmp_path):
        expected = {
            "shaclModel": {"prefixList": [], "shapes": []},
            "matchedSubjects": {"http://example.com/prop": "value"},
        }
        mock_post.return_value = MagicMock(status_code=200, json=lambda: expected)

        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        jsonld = tmp_path / "test.json"
        jsonld.write_text("{}", encoding="utf-8")

        result = convert_and_prefill("http://localhost:8080", shacl, jsonld)
        assert result == expected

    @patch("wizard.api_client.requests.post")
    def test_raises_on_http_error(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=400, text="Bad Input")

        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        jsonld = tmp_path / "test.json"
        jsonld.write_text("{}", encoding="utf-8")

        with pytest.raises(WizardAPIError, match="HTTP 400"):
            convert_and_prefill("http://localhost:8080", shacl, jsonld)

    @patch("wizard.api_client.requests.post")
    def test_raises_on_connection_error(self, mock_post, tmp_path):
        import requests

        mock_post.side_effect = requests.ConnectionError("refused")

        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        jsonld = tmp_path / "test.json"
        jsonld.write_text("{}", encoding="utf-8")

        with pytest.raises(WizardAPIError, match="Cannot connect"):
            convert_and_prefill("http://localhost:8080", shacl, jsonld)


# ── API-backed enrichment tests ──────────────────────────────────────


class TestEnrichFromApi:
    def test_no_change_when_shapes_empty(self):
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing"}
        modified = _enrich_from_api(data, [], {}, [])
        assert modified is False

    @patch("builtins.input", return_value="new value")
    def test_modifies_data_with_user_input(self, mock_input):
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing"}
        shapes = [
            {
                "schema": "ThingShape",
                "constraints": [
                    {
                        "path": {"prefix": "test", "value": "name"},
                        "name": "Name",
                        "description": {"en": "The name"},
                        "minCount": 1,
                        "datatype": {"value": "String"},
                        "in": [],
                        "or": None,
                        "children": None,
                    }
                ],
            }
        ]
        prefix_list = [{"alias": "test", "url": "http://example.com/test/"}]

        modified = _enrich_from_api(data, shapes, {}, prefix_list)
        assert modified is True
        assert data["test:name"] == "new value"

    @patch("builtins.input", return_value="")
    def test_keeps_matched_value_on_empty_input(self, mock_input):
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing", "test:name": "existing"}
        shapes = [
            {
                "schema": "ThingShape",
                "constraints": [
                    {
                        "path": {"prefix": "test", "value": "name"},
                        "name": "Name",
                        "description": {},
                        "minCount": 0,
                        "datatype": {"value": "String"},
                        "in": [],
                        "or": None,
                        "children": None,
                    }
                ],
            }
        ]
        prefix_list = [{"alias": "test", "url": "http://example.com/test/"}]
        matched = {"http://example.com/test/name": "existing"}

        modified = _enrich_from_api(data, shapes, matched, prefix_list)
        assert modified is False
        assert data["test:name"] == "existing"

    @patch("builtins.input", side_effect=["1", "Alice"])
    def test_shor_at_constraint_level_without_path(self, mock_input):
        """sh:or wrapper has no path — branches carry their own paths."""
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing"}
        shapes = [
            {
                "schema": "ThingShape",
                "constraints": [
                    {
                        "name": "Name (choose one)",
                        "description": {},
                        "or": [
                            {
                                "path": {"prefix": "test", "value": "firstName"},
                                "name": "First Name",
                                "minCount": 1,
                                "datatype": {"value": "String"},
                            },
                            {
                                "path": {"prefix": "test", "value": "givenName"},
                                "name": "Given Name",
                                "minCount": 1,
                                "datatype": {"value": "String"},
                            },
                        ],
                    }
                ],
            }
        ]

        modified = _enrich_from_api(data, shapes, {}, [])
        assert modified is True
        # User selected branch 1 (firstName) and entered "Alice"
        assert data["test:firstName"] == "Alice"
        assert "test:givenName" not in data

    @patch("builtins.input", side_effect=[""])
    def test_shor_at_constraint_level_skip(self, mock_input):
        """User presses Enter to skip an sh:or choice — no modification."""
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing"}
        shapes = [
            {
                "schema": "ThingShape",
                "constraints": [
                    {
                        "name": "Name (choose one)",
                        "or": [
                            {
                                "path": {"prefix": "test", "value": "firstName"},
                                "name": "First Name",
                                "datatype": {"value": "String"},
                            },
                        ],
                    }
                ],
            }
        ]

        modified = _enrich_from_api(data, shapes, {}, [])
        assert modified is False

    @patch("builtins.input", side_effect=["1", "Bob"])
    def test_shor_on_property_with_path(self, mock_input):
        """sh:or on a constraint that ALSO has its own path — branch key wins."""
        from wizard.shacl_wizard import _enrich_from_api

        data = {"@type": "test:Thing"}
        shapes = [
            {
                "schema": "ThingShape",
                "constraints": [
                    {
                        "path": {"prefix": "test", "value": "identifier"},
                        "name": "Identifier",
                        "description": {},
                        "or": [
                            {
                                "path": {"prefix": "test", "value": "codeEPSG"},
                                "name": "EPSG code",
                                "minCount": 1,
                                "datatype": {"value": "integer"},
                            },
                            {
                                "path": {
                                    "prefix": "test",
                                    "value": "coordinateSystemName",
                                },
                                "name": "Coordinate system name",
                                "minCount": 1,
                                "datatype": {"value": "String"},
                            },
                        ],
                    }
                ],
            }
        ]

        modified = _enrich_from_api(data, shapes, {}, [])
        assert modified is True
        # Branch key "test:codeEPSG" is used, not the wrapper key "test:identifier"
        assert data["test:codeEPSG"] == "Bob"


# ── main.py fallback logic ───────────────────────────────────────────


class TestMainFallback:
    """Verify that main() falls back to local mode when wizard cannot start."""

    @patch("wizard.shacl_wizard.run_wizard")
    @patch("wizard.api_client.ensure_wizard_running", return_value=None)
    def test_falls_back_to_local_when_api_unreachable(
        self, mock_ensure, mock_run_wizard, tmp_path
    ):
        from wizard.main import main

        jsonld = tmp_path / "test.json"
        jsonld.write_text('{"@type": "test:Thing"}', encoding="utf-8")
        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        out = tmp_path / "out.json"

        with patch(
            "sys.argv",
            [
                "wizard",
                str(jsonld),
                "-shacl",
                str(shacl),
                "-enable",
                "true",
                "-out",
                str(out),
            ],
        ):
            main()

        mock_ensure.assert_called_once()
        mock_run_wizard.assert_called_once()

    def test_env_var_overrides_enable_false(self, tmp_path):
        """WIZARD_ENABLED=true should activate wizard even when config says -enable false."""
        from wizard.main import main

        jsonld = tmp_path / "test.json"
        jsonld.write_text('{"@type": "test:Thing"}', encoding="utf-8")
        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        out = tmp_path / "out.json"

        with (
            patch(
                "sys.argv",
                [
                    "wizard",
                    str(jsonld),
                    "-shacl",
                    str(shacl),
                    "-enable",
                    "false",
                    "-out",
                    str(out),
                ],
            ),
            patch.dict("os.environ", {"WIZARD_ENABLED": "true"}),
            patch(
                "wizard.api_client.ensure_wizard_running", return_value=None
            ) as mock_ensure,
            patch("wizard.main.run_wizard") as mock_run_wizard,
        ):
            main()

        mock_ensure.assert_called_once()
        mock_run_wizard.assert_called_once()

    def test_disabled_when_no_env_var(self, tmp_path):
        """Without WIZARD_ENABLED, -enable false should just copy."""
        from wizard.main import main

        jsonld = tmp_path / "test.json"
        jsonld.write_text('{"@type": "test:Thing"}', encoding="utf-8")
        shacl = tmp_path / "test.ttl"
        shacl.write_text("# empty", encoding="utf-8")
        out = tmp_path / "out.json"

        with (
            patch(
                "sys.argv",
                [
                    "wizard",
                    str(jsonld),
                    "-shacl",
                    str(shacl),
                    "-enable",
                    "false",
                    "-out",
                    str(out),
                ],
            ),
            patch.dict("os.environ", {}, clear=True),
        ):
            main()

        assert out.exists()
        assert out.read_text() == '{"@type": "test:Thing"}'
