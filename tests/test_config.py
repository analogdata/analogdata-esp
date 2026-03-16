"""Tests for analogdata_esp.core.config."""

import sys
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from analogdata_esp.core.config import (
    IDFConfig,
    detect_all_idf,
    detect_idf,
    get_template_dir,
    _read_version,
    _find_python,
)


# ---------------------------------------------------------------------------
# IDFConfig dataclass
# ---------------------------------------------------------------------------

class TestIDFConfig:
    def test_is_valid_true_when_both_paths_exist(self, tmp_path):
        idf_path = tmp_path / "esp-idf"
        idf_path.mkdir()
        python_path = tmp_path / "python3"
        python_path.write_text("#!/usr/bin/env python3")

        cfg = IDFConfig(idf_path=idf_path, python_path=python_path)
        assert cfg.is_valid is True

    def test_is_valid_false_when_idf_path_missing(self, tmp_path):
        missing = tmp_path / "nonexistent"
        python_path = tmp_path / "python3"
        python_path.write_text("#!/usr/bin/env python3")

        cfg = IDFConfig(idf_path=missing, python_path=python_path)
        assert cfg.is_valid is False

    def test_is_valid_false_when_python_path_missing(self, tmp_path):
        idf_path = tmp_path / "esp-idf"
        idf_path.mkdir()
        missing_python = tmp_path / "no_python"

        cfg = IDFConfig(idf_path=idf_path, python_path=missing_python)
        assert cfg.is_valid is False

    def test_is_valid_false_when_both_paths_none(self):
        cfg = IDFConfig()
        assert cfg.is_valid is False

    def test_is_valid_false_when_python_path_none(self, tmp_path):
        idf_path = tmp_path / "esp-idf"
        idf_path.mkdir()
        cfg = IDFConfig(idf_path=idf_path, python_path=None)
        assert cfg.is_valid is False

    def test_default_values(self):
        cfg = IDFConfig()
        assert cfg.idf_path is None
        assert cfg.tools_path is None
        assert cfg.python_path is None
        assert cfg.version is None
        assert cfg.is_valid is False

    def test_version_stored(self, tmp_path):
        idf_path = tmp_path / "esp-idf"
        idf_path.mkdir()
        python_path = tmp_path / "python3"
        python_path.write_text("#!/usr/bin/env python3")
        cfg = IDFConfig(idf_path=idf_path, python_path=python_path, version="v5.2.0")
        assert cfg.version == "v5.2.0"


# ---------------------------------------------------------------------------
# _read_version
# ---------------------------------------------------------------------------

class TestReadVersion:
    def test_reads_version_txt(self, fake_idf_dir):
        version = _read_version(fake_idf_dir)
        assert version == "v5.2.0"

    def test_returns_unknown_when_no_version_file(self, tmp_path):
        idf_dir = tmp_path / "esp-idf"
        idf_dir.mkdir()
        (idf_dir / "tools" / "cmake").mkdir(parents=True)
        version = _read_version(idf_dir)
        assert version == "unknown"

    def test_reads_version_from_cmake_when_no_txt(self, tmp_path):
        idf_dir = tmp_path / "esp-idf"
        cmake_dir = idf_dir / "tools" / "cmake"
        cmake_dir.mkdir(parents=True)
        version_cmake = cmake_dir / "version.cmake"
        version_cmake.write_text("set(IDF_VERSION_MAJOR 5)\nset(IDF_VERSION_MINOR 2)\n")
        version = _read_version(idf_dir)
        assert version == "5.x"

    def test_strips_trailing_newline(self, tmp_path):
        idf_dir = tmp_path / "esp-idf"
        idf_dir.mkdir()
        (idf_dir / "version.txt").write_text("v5.3.1\n")
        version = _read_version(idf_dir)
        assert version == "v5.3.1"


# ---------------------------------------------------------------------------
# _find_python
# ---------------------------------------------------------------------------

class TestFindPython:
    def test_finds_unix_venv_python(self, tmp_path):
        tools_path = tmp_path / "tools"
        python_bin = tools_path / "python" / "v3.11.0" / "venv" / "bin"
        python_bin.mkdir(parents=True)
        py = python_bin / "python3"
        py.write_text("#!/bin/python3")

        result = _find_python(tools_path)
        assert result == py

    def test_falls_back_to_system_python_when_no_venv(self, tmp_path):
        tools_path = tmp_path / "empty_tools"
        tools_path.mkdir()
        result = _find_python(tools_path)
        # Should return a Path (system python fallback)
        assert result is not None
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# detect_all_idf
# ---------------------------------------------------------------------------

class TestDetectAllIdf:
    def test_returns_list(self):
        """detect_all_idf always returns a list (possibly empty)."""
        result = detect_all_idf()
        assert isinstance(result, list)

    def test_detects_fake_idf_via_env_var(self, fake_idf_dir, monkeypatch, tmp_path):
        """IDF_PATH env var should be picked up as a candidate."""
        # Provide a fake python so IDFConfig.is_valid can be True
        python_bin = tmp_path / "tools" / "python" / "v3.11.0" / "venv" / "bin"
        python_bin.mkdir(parents=True)
        py = python_bin / "python3"
        py.write_text("#!/bin/python3")

        monkeypatch.setenv("IDF_PATH", str(fake_idf_dir))
        # Patch HOME-based tools path to our tmp tools
        with patch("analogdata_esp.core.config.HOME", tmp_path):
            results = detect_all_idf()

        # fake_idf_dir has project.cmake, so it should appear
        idf_paths = [r.idf_path for r in results]
        assert fake_idf_dir in idf_paths

    def test_returns_idf_config_objects(self, fake_idf_dir, monkeypatch, tmp_path):
        monkeypatch.setenv("IDF_PATH", str(fake_idf_dir))
        with patch("analogdata_esp.core.config.HOME", tmp_path):
            results = detect_all_idf()
        for r in results:
            assert isinstance(r, IDFConfig)

    def test_skips_duplicate_candidates(self, fake_idf_dir, monkeypatch, tmp_path):
        monkeypatch.setenv("IDF_PATH", str(fake_idf_dir))
        with patch("analogdata_esp.core.config.HOME", tmp_path):
            results = detect_all_idf()
        idf_paths = [r.idf_path for r in results]
        assert len(idf_paths) == len(set(idf_paths))

    def test_missing_project_cmake_excluded(self, tmp_path, monkeypatch):
        """A directory without tools/cmake/project.cmake is not included."""
        bad_idf = tmp_path / "bad-idf"
        bad_idf.mkdir()
        monkeypatch.setenv("IDF_PATH", str(bad_idf))
        with patch("analogdata_esp.core.config.HOME", tmp_path):
            results = detect_all_idf()
        idf_paths = [r.idf_path for r in results]
        assert bad_idf not in idf_paths


# ---------------------------------------------------------------------------
# detect_idf
# ---------------------------------------------------------------------------

class TestDetectIdf:
    def test_returns_idf_config_instance(self):
        result = detect_idf()
        assert isinstance(result, IDFConfig)

    def test_uses_saved_path_when_valid(self, fake_idf_dir, tmp_path, monkeypatch):
        """detect_idf should use the saved path when it points to a valid IDF dir."""
        # Provide a fake python
        python_bin = tmp_path / "tools" / "python" / "v3.11.0" / "venv" / "bin"
        python_bin.mkdir(parents=True)
        py = python_bin / "python3"
        py.write_text("#!/bin/python3")

        with patch("analogdata_esp.core.config.HOME", tmp_path):
            with patch(
                "analogdata_esp.core.settings.get_idf_setting",
                side_effect=lambda key: str(fake_idf_dir) if key == "path" else "",
            ):
                result = detect_idf()

        assert result.idf_path == fake_idf_dir

    def test_falls_back_to_auto_detect_when_saved_path_missing(self, tmp_path, monkeypatch):
        """detect_idf falls back to detect_all_idf when saved path doesn't exist."""
        nonexistent = tmp_path / "nonexistent-idf"

        with patch(
            "analogdata_esp.core.settings.get_idf_setting",
            side_effect=lambda key: str(nonexistent) if key == "path" else "",
        ):
            with patch("analogdata_esp.core.config.detect_all_idf", return_value=[]) as mock_detect:
                result = detect_idf()
                mock_detect.assert_called_once()

        assert isinstance(result, IDFConfig)
        assert result.is_valid is False

    def test_falls_back_when_project_cmake_missing(self, tmp_path):
        """detect_idf falls back when saved path exists but lacks project.cmake."""
        idf_dir = tmp_path / "incomplete-idf"
        idf_dir.mkdir()
        # No tools/cmake/project.cmake

        with patch(
            "analogdata_esp.core.settings.get_idf_setting",
            side_effect=lambda key: str(idf_dir) if key == "path" else "",
        ):
            with patch("analogdata_esp.core.config.detect_all_idf", return_value=[]) as mock_detect:
                result = detect_idf()
                mock_detect.assert_called_once()

        assert result.is_valid is False

    def test_returns_empty_idf_config_when_nothing_found(self):
        with patch(
            "analogdata_esp.core.settings.get_idf_setting",
            return_value="",
        ):
            with patch("analogdata_esp.core.config.detect_all_idf", return_value=[]):
                result = detect_idf()

        assert isinstance(result, IDFConfig)
        assert result.is_valid is False

    def test_returns_first_result_from_auto_detect(self, fake_idf_dir, tmp_path):
        python_bin = tmp_path / "tools" / "python" / "v3.11.0" / "venv" / "bin"
        python_bin.mkdir(parents=True)
        py = python_bin / "python3"
        py.write_text("#!/bin/python3")

        first = IDFConfig(idf_path=fake_idf_dir, python_path=py, version="v5.2.0")
        second = IDFConfig(idf_path=tmp_path / "other", python_path=py, version="v5.1.0")

        with patch("analogdata_esp.core.settings.get_idf_setting", return_value=""):
            with patch("analogdata_esp.core.config.detect_all_idf", return_value=[first, second]):
                result = detect_idf()

        assert result.idf_path == fake_idf_dir


# ---------------------------------------------------------------------------
# get_template_dir
# ---------------------------------------------------------------------------

class TestGetTemplateDir:
    def test_returns_path_object(self):
        result = get_template_dir()
        assert isinstance(result, Path)

    def test_returns_package_templates_dir_normally(self):
        """When not frozen, should return the templates directory near the package."""
        result = get_template_dir()
        # The real templates dir exists in this project
        assert result.name == "templates"

    def test_returns_meipass_templates_when_frozen(self, tmp_path, monkeypatch):
        """When sys.frozen=True and sys._MEIPASS is set, use MEIPASS/templates."""
        fake_meipass = tmp_path / "meipass"
        fake_meipass.mkdir()

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

        result = get_template_dir()
        assert result == fake_meipass / "templates"

    def test_not_frozen_does_not_use_meipass(self, monkeypatch):
        """Without sys.frozen, MEIPASS should not be consulted."""
        monkeypatch.delattr(sys, "frozen", raising=False)
        result = get_template_dir()
        assert result.name == "templates"
        # Should be a real path relative to the package, not a temp MEIPASS path
        assert "analogdata_esp" in str(result) or "analogdata-esp" in str(result)
