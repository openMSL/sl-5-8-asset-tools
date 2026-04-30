"""Tests for the -enable / -disable / -list-modules pipeline flags."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from asset_extraction.main import (
    _config_filename_to_module_id,
    get_configs,
    list_modules,
)

CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


# --- Unit tests for _config_filename_to_module_id ---


class TestConfigFilenameToModuleId:
    def test_strips_prefix_and_suffix(self):
        assert (
            _config_filename_to_module_id("config_vcs_odr-converter.json")
            == "vcs_odr-converter"
        )

    def test_strips_prefix_and_suffix_simple(self):
        assert (
            _config_filename_to_module_id("config_meta_data_extractor.json")
            == "meta_data_extractor"
        )

    def test_no_prefix(self):
        assert _config_filename_to_module_id("something.json") == "something"

    def test_no_suffix(self):
        assert _config_filename_to_module_id("config_foo") == "foo"


# --- Unit tests for list_modules ---


class TestListModules:
    def test_returns_all_modules(self):
        modules = list_modules(CONFIGS_DIR)
        assert len(modules) > 0
        ids = [m["id"] for m in modules]
        assert "vcs_odr-converter" in ids
        assert "xodr_routing_creator" in ids
        assert "structure_creator" in ids

    def test_module_has_expected_keys(self):
        modules = list_modules(CONFIGS_DIR)
        for m in modules:
            assert "id" in m
            assert "filename" in m
            assert "enabled" in m
            assert "extensions" in m

    def test_nonexistent_config_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            list_modules(Path("/nonexistent/path"))


# --- Unit tests for get_configs with enable/disable ---


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Create a minimal config directory for testing."""
    modules = [
        {
            "enable": True,
            "filename": "config_alpha.json",
            "extensions": ["xodr"],
        },
        {
            "enable": True,
            "filename": "config_beta.json",
            "extensions": ["xodr"],
        },
        {
            "enable": True,
            "filename": "config_gamma.json",
        },
        {
            "enable": False,
            "filename": "config_delta.json",
            "extensions": ["xodr"],
        },
    ]
    process = {"config_files": modules}
    (tmp_path / "process.json").write_text(json.dumps(process))

    for m in modules:
        config = {
            "name": m["filename"].removesuffix(".json"),
            "environment type": "python",
            "data folder": "temp",
            "params": {"call": "dummy.main"},
        }
        (tmp_path / m["filename"]).write_text(json.dumps(config))

    return tmp_path


@pytest.fixture
def dummy_xodr(tmp_path):
    """Create a dummy .xodr file."""
    f = tmp_path / "test.xodr"
    f.write_text("<OpenDRIVE/>")
    return f


class TestGetConfigsEnableDisable:
    def test_default_behavior_no_flags(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(tmp_config_dir, dummy_xodr)
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        # alpha, beta enabled + extension match; gamma enabled + no extension filter
        assert "alpha" in ids
        assert "beta" in ids
        assert "gamma" in ids
        # delta is disabled in process.json
        assert "delta" not in ids

    def test_enable_whitelist(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, enable_modules=["alpha"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert ids == ["alpha"]

    def test_enable_whitelist_multiple(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, enable_modules=["alpha", "gamma"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert "alpha" in ids
        assert "gamma" in ids
        assert "beta" not in ids

    def test_enable_can_activate_disabled_module(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, enable_modules=["delta"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert "delta" in ids

    def test_disable_blacklist(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, disable_modules=["beta"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert "alpha" in ids
        assert "gamma" in ids
        assert "beta" not in ids

    def test_disable_multiple(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, disable_modules=["alpha", "gamma"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert ids == ["beta"]

    def test_disable_nonexistent_module_is_harmless(self, tmp_config_dir, dummy_xodr):
        configs, filenames = get_configs(
            tmp_config_dir, dummy_xodr, disable_modules=["nonexistent"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        assert "alpha" in ids
        assert "beta" in ids
        assert "gamma" in ids

    def test_enable_respects_extension_filter(self, tmp_config_dir, dummy_xodr):
        # gamma has no extension filter so it always matches
        # Create a .xosc file — alpha/beta/delta won't match
        xosc_file = dummy_xodr.parent / "test.xosc"
        xosc_file.write_text("<OpenSCENARIO/>")
        configs, filenames = get_configs(
            tmp_config_dir, xosc_file, enable_modules=["alpha", "gamma"]
        )
        ids = [_config_filename_to_module_id(f) for f in filenames.values()]
        # alpha has extensions: ["xodr"] so it won't match .xosc
        assert "alpha" not in ids
        assert "gamma" in ids


# --- CLI integration test for -list-modules ---


class TestListModulesCLI:
    def test_list_modules_exits_zero(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "asset_extraction.main",
                "-config",
                str(CONFIGS_DIR),
                "-list-modules",
            ],
            capture_output=True,
            text=True,
            cwd=str(CONFIGS_DIR.parent),
        )
        assert result.returncode == 0
        assert "vcs_odr-converter" in result.stdout
        assert "MODULE ID" in result.stdout

    def test_enable_disable_mutually_exclusive(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "asset_extraction.main",
                "dummy.json",
                "-config",
                str(CONFIGS_DIR),
                "-out",
                "/tmp/out",
                "-enable",
                "alpha",
                "-disable",
                "beta",
            ],
            capture_output=True,
            text=True,
            cwd=str(CONFIGS_DIR.parent),
        )
        assert result.returncode != 0
        assert "mutually exclusive" in result.stderr


# ── Asset name validation tests ──────────────────────────────────────

from asset_extraction.main import _validate_asset_name


class TestValidateAssetName:
    """Cross-platform filename safety checks."""

    def test_normal_name_passes(self):
        _validate_asset_name("StraightRoad_NCAP")

    def test_dots_in_name_allowed(self):
        _validate_asset_name("deceleration_plot_ve0_25_gx_0.25")
        _validate_asset_name("cutin_plot_03_ve0_60_dv0_30_dx0_15.0_vy_1.8")

    def test_hyphens_and_uppercase(self):
        _validate_asset_name("SCEN-95B774BAC0A9")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            _validate_asset_name("")

    def test_too_long_rejected(self):
        with pytest.raises(ValueError, match="too long"):
            _validate_asset_name("a" * 256)

    def test_max_length_allowed(self):
        _validate_asset_name("a" * 255)

    def test_unsafe_chars_rejected(self):
        for char in '<>:"/\\|?*':
            with pytest.raises(ValueError, match="unsafe"):
                _validate_asset_name(f"test{char}name")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="unsafe"):
            _validate_asset_name("test\x00name")

    def test_windows_reserved_names_rejected(self):
        for name in ["CON", "con", "PRN", "AUX", "NUL", "COM1", "LPT9"]:
            with pytest.raises(ValueError, match="reserved"):
                _validate_asset_name(name)

    def test_reserved_with_extension_rejected(self):
        with pytest.raises(ValueError, match="reserved"):
            _validate_asset_name("CON.xodr")

    def test_trailing_space_rejected(self):
        with pytest.raises(ValueError, match="end with"):
            _validate_asset_name("test ")

    def test_trailing_period_rejected(self):
        with pytest.raises(ValueError, match="end with"):
            _validate_asset_name("test.")

    def test_leading_dot_allowed(self):
        # Hidden files on Unix are unusual but not invalid
        _validate_asset_name(".hidden_asset")
