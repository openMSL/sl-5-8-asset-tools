"""Tests for scripts.init_manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.init_manifest import build_manifest, generate_manifest, scan_directory


@pytest.fixture()
def asset_dir(tmp_path: Path) -> Path:
    """Create a minimal asset directory with an xodr, docs, and LICENSE."""
    (tmp_path / "Town01.xodr").write_text("<OpenDRIVE/>")
    (tmp_path / "docs.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "preview.png").write_bytes(b"\x89PNG")
    (tmp_path / "LICENSE").write_text("MIT")
    return tmp_path


@pytest.fixture()
def scenario_dir(tmp_path: Path) -> Path:
    """Create a scenario asset directory."""
    d = tmp_path / "scenario"
    d.mkdir()
    (d / "test.xosc").write_text("<OpenSCENARIO/>")
    (d / "test.json").write_text("{}")
    (d / "LICENSE.txt").write_text("Apache 2.0")
    return d


class TestScanDirectory:
    def test_classifies_xodr(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        sim = [e for e in entries if e["category"] == "isSimulationData"]
        assert len(sim) == 1
        assert sim[0]["path"] == "Town01.xodr"
        assert sim[0]["mime"] == "application/xml"

    def test_classifies_license(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        lic = [e for e in entries if e["category"] == "license"]
        assert len(lic) == 1
        assert lic[0]["path"] == "LICENSE"
        assert lic[0]["mime"] == "text/plain"

    def test_classifies_docs(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        docs = [e for e in entries if e["category"] == "isDocumentation"]
        assert len(docs) == 1
        assert docs[0]["path"] == "docs.pdf"

    def test_classifies_media(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        media = [e for e in entries if e["category"] == "isMedia"]
        assert len(media) == 1
        assert media[0]["path"] == "preview.png"

    def test_skips_hidden_and_manifest(self, asset_dir: Path) -> None:
        (asset_dir / ".hidden").write_text("")
        (asset_dir / "input_manifest.json").write_text("{}")
        entries = scan_directory(asset_dir)
        names = [e["path"] for e in entries]
        assert ".hidden" not in names
        assert "input_manifest.json" not in names

    def test_skips_subdirectories(self, asset_dir: Path) -> None:
        (asset_dir / "subdir").mkdir()
        (asset_dir / "subdir" / "nested.xodr").write_text("</>")
        entries = scan_directory(asset_dir)
        names = [e["path"] for e in entries]
        assert "nested.xodr" not in names

    def test_classifies_xosc(self, scenario_dir: Path) -> None:
        entries = scan_directory(scenario_dir)
        sim = [e for e in entries if e["category"] == "isSimulationData"]
        assert len(sim) == 1
        assert sim[0]["path"] == "test.xosc"

    def test_json_companion_as_media(self, scenario_dir: Path) -> None:
        entries = scan_directory(scenario_dir)
        media = [e for e in entries if e["category"] == "isMedia"]
        assert any(e["path"] == "test.json" for e in media)

    def test_license_txt_variant(self, scenario_dir: Path) -> None:
        entries = scan_directory(scenario_dir)
        lic = [e for e in entries if e["category"] == "license"]
        assert len(lic) == 1
        assert lic[0]["path"] == "LICENSE.txt"

    def test_3dmodel_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "model.zip").write_bytes(b"PK")
        (tmp_path / "model.7z").write_bytes(b"7z")
        entries = scan_directory(tmp_path)
        assert len(entries) == 2
        assert all(e["category"] == "isSimulationData" for e in entries)


class TestBuildManifest:
    def test_structure(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        manifest = build_manifest(entries)
        assert manifest["@type"] == "envited-x:Manifest"
        assert "@context" in manifest
        assert "hasArtifacts" in manifest
        assert "hasLicense" in manifest

    def test_license_always_public(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        manifest = build_manifest(entries, access_role="isOwner")
        assert manifest["hasLicense"]["hasAccessRole"] == "envited-x:isPublic"

    def test_access_role_propagates(self, asset_dir: Path) -> None:
        entries = scan_directory(asset_dir)
        manifest = build_manifest(entries, access_role="isPublic")
        for art in manifest["hasArtifacts"]:
            assert art["hasAccessRole"] == "envited-x:isPublic"


class TestGenerateManifest:
    def test_creates_file(self, asset_dir: Path) -> None:
        path = generate_manifest(asset_dir)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["@type"] == "envited-x:Manifest"

    def test_refuses_overwrite(self, asset_dir: Path) -> None:
        generate_manifest(asset_dir)
        with pytest.raises(FileExistsError, match="already exists"):
            generate_manifest(asset_dir)

    def test_force_overwrite(self, asset_dir: Path) -> None:
        generate_manifest(asset_dir)
        path = generate_manifest(asset_dir, force=True)
        assert path.exists()

    def test_error_no_sim_data(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello")
        with pytest.raises(ValueError, match="No simulation data"):
            generate_manifest(tmp_path)

    def test_error_not_a_dir(self, tmp_path: Path) -> None:
        fake = tmp_path / "nope"
        with pytest.raises(FileNotFoundError, match="Not a directory"):
            generate_manifest(fake)

    def test_custom_output(self, asset_dir: Path) -> None:
        out = asset_dir / "custom" / "manifest.json"
        path = generate_manifest(asset_dir, output=out)
        assert path == out
        assert out.exists()
