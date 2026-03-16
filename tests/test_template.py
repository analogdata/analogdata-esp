"""Tests for analogdata_esp.core.template (scaffold_project)."""

import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from analogdata_esp.core.template import (
    scaffold_project,
    _render_template,
    SUPPORTED_TARGETS,
)

# Real templates directory at the project root (where esp32-default actually lives)
REAL_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _real_template_dir():
    """Return the actual esp32-default template directory."""
    return REAL_TEMPLATES_DIR


# ---------------------------------------------------------------------------
# SUPPORTED_TARGETS
# ---------------------------------------------------------------------------

class TestSupportedTargets:
    def test_contains_esp32(self):
        assert "esp32" in SUPPORTED_TARGETS

    def test_contains_esp32s3(self):
        assert "esp32s3" in SUPPORTED_TARGETS

    def test_contains_esp32c3(self):
        assert "esp32c3" in SUPPORTED_TARGETS

    def test_all_entries_are_strings(self):
        assert all(isinstance(t, str) for t in SUPPORTED_TARGETS)


# ---------------------------------------------------------------------------
# _render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    def test_replaces_project_name_in_txt_file(self, tmp_path):
        txt = tmp_path / "CMakeLists.txt"
        txt.write_text("project({{ project_name }})\n", encoding="utf-8")
        _render_template(tmp_path, {"project_name": "my_app", "target": "esp32"})
        assert "my_app" in txt.read_text()
        assert "{{" not in txt.read_text()

    def test_replaces_target_in_c_file(self, tmp_path):
        c_file = tmp_path / "main.c"
        c_file.write_text("/* target: {{ target }} */\n", encoding="utf-8")
        _render_template(tmp_path, {"project_name": "demo", "target": "esp32s3"})
        content = c_file.read_text()
        assert "esp32s3" in content
        assert "{{" not in content

    def test_replaces_both_variables(self, tmp_path):
        c_file = tmp_path / "main.c"
        c_file.write_text(
            "// Project: {{ project_name }}, Target: {{ target }}\n",
            encoding="utf-8",
        )
        _render_template(tmp_path, {"project_name": "blink", "target": "esp32c3"})
        content = c_file.read_text()
        assert "blink" in content
        assert "esp32c3" in content

    def test_nested_directory_files_rendered(self, tmp_path):
        subdir = tmp_path / "main"
        subdir.mkdir()
        c_file = subdir / "main.c"
        c_file.write_text("{{ project_name }}", encoding="utf-8")
        _render_template(tmp_path, {"project_name": "nested_app", "target": "esp32"})
        assert "nested_app" in c_file.read_text()

    def test_skips_files_without_jinja_markers(self, tmp_path):
        plain = tmp_path / "plain.txt"
        original = "No templates here.\n"
        plain.write_text(original, encoding="utf-8")
        _render_template(tmp_path, {"project_name": "x", "target": "y"})
        assert plain.read_text() == original

    def test_skips_non_renderable_extension(self, tmp_path):
        # .bin files should not be processed
        binary_file = tmp_path / "data.bin"
        binary_file.write_bytes(b"\x00\x01\x02{{ project_name }}")
        _render_template(tmp_path, {"project_name": "proj", "target": "esp32"})
        # File should be unchanged (not rendered as text)
        assert binary_file.read_bytes() == b"\x00\x01\x02{{ project_name }}"

    def test_multiple_txt_files_all_rendered(self, tmp_path):
        for i in range(3):
            f = tmp_path / f"file{i}.txt"
            # Use string concatenation to avoid Python f-string eating {{ }}
            f.write_text("Name {{ project_name }} " + str(i), encoding="utf-8")
        _render_template(tmp_path, {"project_name": "multi", "target": "esp32"})
        for i in range(3):
            content = (tmp_path / f"file{i}.txt").read_text()
            assert "multi" in content


# ---------------------------------------------------------------------------
# scaffold_project
# ---------------------------------------------------------------------------

class TestScaffoldProject:
    """
    Tests for scaffold_project.

    Two patches are always applied:
      - idf_config.is_valid = False  (prevents real idf.py invocations)
      - get_template_dir() returns REAL_TEMPLATES_DIR (the repo-root templates/)

    The second patch is needed because get_template_dir() normally returns
    analogdata_esp/templates (package subdir) which doesn't exist during tests;
    the real templates live at the project root.
    """

    def _patches(self, valid_idf: bool = False):
        """Return a list of context-manager patches to apply together."""
        from contextlib import ExitStack, contextmanager

        @contextmanager
        def _combined():
            mock_cfg = MagicMock()
            mock_cfg.is_valid = valid_idf
            with patch("analogdata_esp.core.template.idf_config", mock_cfg):
                with patch(
                    "analogdata_esp.core.template.get_template_dir",
                    return_value=REAL_TEMPLATES_DIR,
                ):
                    yield mock_cfg

        return _combined()

    def test_creates_project_directory(self, tmp_path):
        with self._patches():
            result = scaffold_project(
                "my_project", "esp32", tmp_path, git_init=False
            )
        assert result.exists()
        assert result.is_dir()
        assert result.name == "my_project"

    def test_returns_project_path(self, tmp_path):
        with self._patches():
            result = scaffold_project("blink", "esp32", tmp_path, git_init=False)
        assert result == tmp_path / "blink"

    def test_creates_cmake_lists(self, tmp_path):
        with self._patches():
            project_dir = scaffold_project(
                "hello_world", "esp32", tmp_path, git_init=False
            )
        cmake = project_dir / "CMakeLists.txt"
        assert cmake.exists()

    def test_renders_project_name_in_cmake(self, tmp_path):
        with self._patches():
            project_dir = scaffold_project(
                "sensor_app", "esp32", tmp_path, git_init=False
            )
        cmake = project_dir / "CMakeLists.txt"
        content = cmake.read_text()
        assert "sensor_app" in content
        assert "{{" not in content

    def test_renders_project_name_in_main_c(self, tmp_path):
        with self._patches():
            project_dir = scaffold_project(
                "motor_ctrl", "esp32s3", tmp_path, git_init=False
            )
        main_c = project_dir / "main" / "main.c"
        content = main_c.read_text()
        assert "motor_ctrl" in content
        assert "{{" not in content

    def test_renders_target_in_main_c(self, tmp_path):
        with self._patches():
            project_dir = scaffold_project(
                "ble_demo", "esp32c3", tmp_path, git_init=False
            )
        main_c = project_dir / "main" / "main.c"
        content = main_c.read_text()
        assert "esp32c3" in content

    def test_raises_file_exists_error_if_project_exists(self, tmp_path):
        existing = tmp_path / "existing_project"
        existing.mkdir()
        with self._patches():
            with pytest.raises(FileExistsError, match="existing_project"):
                scaffold_project("existing_project", "esp32", tmp_path, git_init=False)

    def test_raises_file_not_found_when_template_missing(self, tmp_path):
        fake_template_dir = tmp_path / "no_templates"
        fake_template_dir.mkdir()

        mock_cfg = MagicMock()
        mock_cfg.is_valid = False
        with patch("analogdata_esp.core.template.idf_config", mock_cfg):
            with patch(
                "analogdata_esp.core.template.get_template_dir",
                return_value=fake_template_dir,
            ):
                with pytest.raises(FileNotFoundError, match="esp32-default"):
                    scaffold_project("newproj", "esp32", tmp_path, git_init=False)

    def test_git_init_called_when_enabled(self, tmp_path):
        with self._patches():
            with patch("analogdata_esp.core.template._git_init") as mock_git:
                scaffold_project("git_project", "esp32", tmp_path, git_init=True)
                mock_git.assert_called_once()

    def test_git_init_not_called_when_disabled(self, tmp_path):
        with self._patches():
            with patch("analogdata_esp.core.template._git_init") as mock_git:
                scaffold_project("no_git_project", "esp32", tmp_path, git_init=False)
                mock_git.assert_not_called()

    def test_idf_setup_not_called_when_idf_invalid(self, tmp_path):
        with self._patches():
            with patch("analogdata_esp.core.template._run_idf_setup") as mock_idf:
                scaffold_project("no_idf", "esp32", tmp_path, git_init=False)
                mock_idf.assert_not_called()

    def test_idf_setup_called_when_idf_valid(self, tmp_path):
        with patch(
            "analogdata_esp.core.template.get_template_dir",
            return_value=REAL_TEMPLATES_DIR,
        ):
            valid_cfg = MagicMock()
            valid_cfg.is_valid = True
            with patch("analogdata_esp.core.template.idf_config", valid_cfg):
                with patch("analogdata_esp.core.template._run_idf_setup") as mock_idf:
                    scaffold_project("with_idf", "esp32", tmp_path, git_init=False)
                    mock_idf.assert_called_once_with(tmp_path / "with_idf", "esp32")

    def test_template_files_copied(self, tmp_path):
        """All files from esp32-default template should appear in new project."""
        with self._patches():
            project_dir = scaffold_project("full_copy", "esp32", tmp_path, git_init=False)

        assert (project_dir / "CMakeLists.txt").exists()
        assert (project_dir / "main" / "main.c").exists()
        assert (project_dir / "main" / "CMakeLists.txt").exists()

    def test_different_targets_rendered_correctly(self, tmp_path):
        targets = ["esp32", "esp32s3", "esp32c3", "esp32h2"]
        for i, target in enumerate(targets):
            with self._patches():
                project_dir = scaffold_project(
                    f"proj_{i}", target, tmp_path, git_init=False
                )
            main_c = project_dir / "main" / "main.c"
            assert target in main_c.read_text()
