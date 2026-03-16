"""Tests for analogdata_esp.agent.context."""

import pytest
from pathlib import Path

from analogdata_esp.agent.context import (
    collect_context,
    ProjectContext,
    _extract_errors,
    _read_build_error,
)


# ---------------------------------------------------------------------------
# _extract_errors
# ---------------------------------------------------------------------------

class TestExtractErrors:
    def test_extracts_error_colon_lines(self):
        content = "main.c:10:5: error: 'foo' undeclared\nnormal line\n"
        result = _extract_errors(content)
        assert len(result) == 1
        assert "error:" in result[0].lower()

    def test_extracts_undefined_reference(self):
        content = "undefined reference to 'gpio_set_level'\n"
        result = _extract_errors(content)
        assert len(result) == 1
        assert "undefined" in result[0].lower()

    def test_extracts_fatal_colon(self):
        content = "fatal: could not open source file\n"
        result = _extract_errors(content)
        assert len(result) == 1
        assert "fatal:" in result[0].lower()

    def test_extracts_cmake_error(self):
        content = "CMake Error at CMakeLists.txt:3: message\n"
        result = _extract_errors(content)
        assert len(result) == 1

    def test_extracts_ninja_line(self):
        content = "ninja: build stopped: subcommand failed.\n"
        result = _extract_errors(content)
        assert len(result) == 1
        assert "ninja:" in result[0].lower()

    def test_ignores_normal_lines(self):
        content = (
            "-- Configuring done\n"
            "-- Build files written to /tmp/build\n"
            "Linking CXX executable app.elf\n"
        )
        result = _extract_errors(content)
        assert result == []

    def test_returns_empty_for_empty_content(self):
        assert _extract_errors("") == []

    def test_strips_whitespace_from_lines(self):
        content = "   main.c:1: error: missing semicolon   \n"
        result = _extract_errors(content)
        assert result[0] == "main.c:1: error: missing semicolon"

    def test_multiple_error_lines(self):
        content = (
            "file1.c:1: error: foo\n"
            "file2.c:2: error: bar\n"
            "unrelated line\n"
            "undefined reference to baz\n"
        )
        result = _extract_errors(content)
        assert len(result) == 3

    def test_case_insensitive_matching(self):
        content = "ERROR: Something went wrong\nFATAL: Critical failure\n"
        result = _extract_errors(content)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# ProjectContext.as_text
# ---------------------------------------------------------------------------

class TestProjectContextAsText:
    def test_empty_context_returns_empty_string(self):
        ctx = ProjectContext()
        assert ctx.as_text() == ""

    def test_formats_project_name(self):
        ctx = ProjectContext(project_name="blink")
        text = ctx.as_text()
        assert "blink" in text
        assert "Project:" in text

    def test_formats_target_chip(self):
        ctx = ProjectContext(idf_target="esp32s3")
        text = ctx.as_text()
        assert "esp32s3" in text
        assert "Target chip:" in text

    def test_formats_idf_version(self):
        ctx = ProjectContext(idf_version="v5.2.0")
        text = ctx.as_text()
        assert "v5.2.0" in text
        assert "ESP-IDF version:" in text

    def test_formats_all_fields(self):
        ctx = ProjectContext(
            project_name="my_app",
            idf_target="esp32c3",
            idf_version="v5.1.0",
        )
        text = ctx.as_text()
        assert "my_app" in text
        assert "esp32c3" in text
        assert "v5.1.0" in text

    def test_only_present_fields_included(self):
        ctx = ProjectContext(project_name="minimal")
        text = ctx.as_text()
        assert "Target chip:" not in text
        assert "ESP-IDF version:" not in text

    def test_fields_on_separate_lines(self):
        ctx = ProjectContext(
            project_name="demo",
            idf_target="esp32",
            idf_version="v5.2.0",
        )
        lines = ctx.as_text().splitlines()
        assert len(lines) == 3

    def test_build_error_not_included_in_as_text(self):
        """build_error is separate from as_text() output."""
        ctx = ProjectContext(
            project_name="proj",
            build_error="error: something failed",
        )
        text = ctx.as_text()
        assert "error: something failed" not in text


# ---------------------------------------------------------------------------
# collect_context
# ---------------------------------------------------------------------------

class TestCollectContext:
    def test_returns_project_context_instance(self, tmp_project_dir):
        result = collect_context(tmp_project_dir)
        assert isinstance(result, ProjectContext)

    def test_reads_project_name_from_cmake(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        assert ctx.project_name == "test_blink"

    def test_reads_target_from_sdkconfig(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        assert ctx.idf_target == "esp32"

    def test_reads_idf_version_from_sdkconfig(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        assert ctx.idf_version == "v5.2.0"

    def test_reads_build_errors_from_log(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        assert ctx.build_error is not None
        assert len(ctx.build_error) > 0

    def test_build_error_contains_error_lines(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        # The fixture has lines with "error:" and "undefined" and "fatal:"
        assert "error" in ctx.build_error.lower()

    def test_has_build_true_when_sdkconfig_exists(self, tmp_project_dir):
        ctx = collect_context(tmp_project_dir)
        assert ctx.has_build is True

    def test_empty_context_when_no_files(self, tmp_path):
        empty_dir = tmp_path / "empty_project"
        empty_dir.mkdir()
        ctx = collect_context(empty_dir)
        assert ctx.project_name is None
        assert ctx.idf_target is None
        assert ctx.idf_version is None
        assert ctx.build_error is None
        assert ctx.has_build is False

    def test_no_cmake_project_name_is_none(self, tmp_path):
        project_dir = tmp_path / "no_cmake"
        project_dir.mkdir()
        # sdkconfig but no CMakeLists.txt
        (project_dir / "sdkconfig").write_text(
            'CONFIG_IDF_TARGET="esp32"\nCONFIG_IDF_VER="v5.2.0"\n'
        )
        ctx = collect_context(project_dir)
        assert ctx.project_name is None
        assert ctx.idf_target == "esp32"

    def test_cmake_without_project_call(self, tmp_path):
        project_dir = tmp_path / "no_project_call"
        project_dir.mkdir()
        (project_dir / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\n"
        )
        ctx = collect_context(project_dir)
        assert ctx.project_name is None

    def test_no_sdkconfig_target_is_none(self, tmp_path):
        project_dir = tmp_path / "no_sdkconfig"
        project_dir.mkdir()
        (project_dir / "CMakeLists.txt").write_text("project(myproj)\n")
        ctx = collect_context(project_dir)
        assert ctx.idf_target is None
        assert ctx.idf_version is None
        assert ctx.has_build is False

    def test_no_build_log_build_error_is_none(self, tmp_path):
        project_dir = tmp_path / "no_build_log"
        project_dir.mkdir()
        (project_dir / "CMakeLists.txt").write_text("project(myproj)\n")
        ctx = collect_context(project_dir)
        assert ctx.build_error is None

    def test_uses_cwd_when_no_path_given(self, tmp_project_dir, monkeypatch):
        monkeypatch.chdir(tmp_project_dir)
        ctx = collect_context()
        assert ctx.project_name == "test_blink"

    def test_build_error_limited_to_50_lines(self, tmp_path):
        """_read_build_error should return last 50 lines of errors."""
        project_dir = tmp_path / "big_errors"
        project_dir.mkdir()
        log_dir = project_dir / "build" / "log"
        log_dir.mkdir(parents=True)
        # Write 100 error lines
        lines = "\n".join(f"file.c:{i}: error: some error {i}" for i in range(100))
        (log_dir / "idf_py_stderr_output").write_text(lines)

        ctx = collect_context(project_dir)
        assert ctx.build_error is not None
        result_lines = ctx.build_error.splitlines()
        assert len(result_lines) <= 50

    def test_fallback_to_build_log_files(self, tmp_path):
        """Falls back to build/*.log when idf_py_stderr_output is absent."""
        project_dir = tmp_path / "fallback_log"
        project_dir.mkdir()
        build_dir = project_dir / "build"
        build_dir.mkdir()
        log_file = build_dir / "build.log"
        log_file.write_text("undefined reference to 'missing_func'\n")

        ctx = collect_context(project_dir)
        assert ctx.build_error is not None
        assert "undefined" in ctx.build_error.lower()

    def test_project_name_with_underscores(self, tmp_path):
        project_dir = tmp_path / "underscore_proj"
        project_dir.mkdir()
        (project_dir / "CMakeLists.txt").write_text("project(my_sensor_app)\n")
        ctx = collect_context(project_dir)
        assert ctx.project_name == "my_sensor_app"

    def test_sdkconfig_with_additional_config_lines(self, tmp_path):
        """sdkconfig with many lines still parses target and version correctly."""
        project_dir = tmp_path / "big_sdkconfig"
        project_dir.mkdir()
        lines = [
            "CONFIG_FREERTOS_HZ=100",
            'CONFIG_IDF_TARGET="esp32s3"',
            "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y",
            'CONFIG_IDF_VER="v5.3.0"',
            "CONFIG_SPIRAM=y",
        ]
        (project_dir / "sdkconfig").write_text("\n".join(lines))
        ctx = collect_context(project_dir)
        assert ctx.idf_target == "esp32s3"
        assert ctx.idf_version == "v5.3.0"
