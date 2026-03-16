"""
Tests for build / flash / monitor / menuconfig commands and idf_runner helpers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from analogdata_esp.main import app
from analogdata_esp.core.idf_runner import (
    build_idf_env,
    detect_serial_ports,
    pick_port,
)
from analogdata_esp.commands.doctor import _find_toolchain
from analogdata_esp.core.config import IDFConfig

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _fake_cfg(tmp_path: Path) -> IDFConfig:
    """Minimal valid IDFConfig pointing at a temp directory."""
    idf = tmp_path / "esp-idf"
    idf.mkdir()
    (idf / "tools" / "cmake").mkdir(parents=True)
    (idf / "tools" / "cmake" / "project.cmake").write_text("")
    (idf / "version.txt").write_text("v5.2.0")
    idf_py = idf / "tools" / "idf.py"
    idf_py.write_text("#!/usr/bin/env python3\nprint('fake idf.py')\n")

    python = tmp_path / "venv" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    python.write_text("")
    python.chmod(0o755)

    return IDFConfig(
        idf_path=idf,
        tools_path=tmp_path / "tools",
        python_path=python,
        version="v5.2.0",
    )


# ─────────────────────────────────────────────────────────────────────────────
# idf_runner — build_idf_env
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildIdfEnv:
    def test_returns_dict(self, tmp_path):
        cfg = _fake_cfg(tmp_path)
        env = build_idf_env(cfg)
        assert isinstance(env, dict)

    def test_sets_idf_path(self, tmp_path):
        cfg = _fake_cfg(tmp_path)
        env = build_idf_env(cfg)
        assert env["IDF_PATH"] == str(cfg.idf_path)

    def test_prepends_venv_bin_to_path(self, tmp_path):
        cfg = _fake_cfg(tmp_path)
        env = build_idf_env(cfg)
        # venv/bin should be at the start of PATH
        path_entries = env["PATH"].split(":")
        venv_bin = str(cfg.python_path.parent)
        assert venv_bin in path_entries
        assert path_entries.index(venv_bin) < path_entries.index(path_entries[-1])

    def test_invalid_cfg_returns_env_without_crash(self):
        cfg = IDFConfig()  # is_valid = False
        env = build_idf_env(cfg)
        assert isinstance(env, dict)
        assert "IDF_PATH" not in env


# ─────────────────────────────────────────────────────────────────────────────
# idf_runner — serial port detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectSerialPorts:
    def test_returns_list(self):
        ports = detect_serial_ports()
        assert isinstance(ports, list)

    def test_all_entries_are_strings(self):
        ports = detect_serial_ports()
        assert all(isinstance(p, str) for p in ports)

    def test_pick_port_respects_override(self):
        assert pick_port("/dev/ttyUSB99") == "/dev/ttyUSB99"

    def test_pick_port_returns_none_when_no_ports(self):
        with patch("analogdata_esp.core.idf_runner.detect_serial_ports", return_value=[]):
            result = pick_port(None)
        assert result is None

    def test_pick_port_returns_first_detected(self):
        with patch(
            "analogdata_esp.core.idf_runner.detect_serial_ports",
            return_value=["/dev/ttyUSB0", "/dev/ttyUSB1"],
        ):
            result = pick_port(None)
        assert result == "/dev/ttyUSB0"


# ─────────────────────────────────────────────────────────────────────────────
# idf_runner — _find_toolchain
# ─────────────────────────────────────────────────────────────────────────────

class TestFindToolchain:
    def test_finds_on_path(self):
        with patch("shutil.which", return_value="/usr/bin/gcc"):
            result = _find_toolchain("gcc")
        assert result == Path("/usr/bin/gcc")

    def test_returns_none_when_missing(self, tmp_path):
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        with patch("shutil.which", return_value=None), \
             patch("analogdata_esp.commands.doctor._TOOLS_ROOTS", [empty_root]):
            result = _find_toolchain("xtensa-esp32-elf-gcc")
        assert result is None

    def test_finds_in_tools_dir(self, tmp_path):
        # Build a fake tools structure:
        # tmp_path/xtensa-esp-elf/esp-14.2.0/xtensa-esp-elf/bin/xtensa-esp32-elf-gcc
        bin_dir = tmp_path / "xtensa-esp-elf" / "esp-14.2.0" / "xtensa-esp-elf" / "bin"
        bin_dir.mkdir(parents=True)
        binary = bin_dir / "xtensa-esp32-elf-gcc"
        binary.write_text("")

        with patch("shutil.which", return_value=None), \
             patch("analogdata_esp.commands.doctor._TOOLS_ROOTS", [tmp_path]):
            result = _find_toolchain("xtensa-esp32-elf-gcc")

        assert result == binary


# ─────────────────────────────────────────────────────────────────────────────
# CLI — build command
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCommand:
    def test_help(self):
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "build" in result.output.lower()

    def test_fails_without_idf(self, tmp_path):
        with patch(
            "analogdata_esp.commands.build.detect_idf",
            return_value=IDFConfig(),
        ):
            result = runner.invoke(app, ["build", "--dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "ESP-IDF" in result.output

    def test_streams_output_on_success(self, tmp_path):
        fake_lines = ["Compiling main.c", "Linking firmware.elf", "Project build complete"]

        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.run_idf_streaming", return_value=iter(fake_lines)):
            mock_idf.return_value = _fake_cfg(tmp_path)
            result = runner.invoke(app, ["build", "--dir", str(tmp_path)])

        assert "Build successful" in result.output

    def test_reports_failure_on_error_exit(self, tmp_path):
        fake_lines = ["main.c:5: error: undeclared", "[exit code 1]"]

        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.run_idf_streaming", return_value=iter(fake_lines)):
            mock_idf.return_value = _fake_cfg(tmp_path)
            result = runner.invoke(app, ["build", "--dir", str(tmp_path)])

        assert "failed" in result.output.lower() or result.exit_code != 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI — flash command
# ─────────────────────────────────────────────────────────────────────────────

class TestFlashCommand:
    def test_help(self):
        result = runner.invoke(app, ["flash", "--help"])
        assert result.exit_code == 0
        assert "flash" in result.output.lower()

    def test_fails_without_idf(self, tmp_path):
        with patch(
            "analogdata_esp.commands.build.detect_idf",
            return_value=IDFConfig(),
        ):
            result = runner.invoke(app, ["flash", "--port", "/dev/ttyUSB0",
                                          "--dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_fails_when_no_port(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.pick_port", return_value=None):
            mock_idf.return_value = _fake_cfg(tmp_path)
            result = runner.invoke(app, ["flash", "--dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "port" in result.output.lower()

    def test_calls_interactive_with_port(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.pick_port", return_value="/dev/ttyUSB0"), \
             patch("analogdata_esp.commands.build.run_idf_interactive", return_value=0) as mock_run:
            mock_idf.return_value = _fake_cfg(tmp_path)
            result = runner.invoke(app, ["flash", "--dir", str(tmp_path)])

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]   # positional args[0] = idf args list
        assert "-p" in call_args
        assert "/dev/ttyUSB0" in call_args
        assert "flash" in call_args


# ─────────────────────────────────────────────────────────────────────────────
# CLI — monitor command
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitorCommand:
    def test_help(self):
        result = runner.invoke(app, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_fails_when_no_port(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.pick_port", return_value=None):
            mock_idf.return_value = _fake_cfg(tmp_path)
            result = runner.invoke(app, ["monitor", "--dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_calls_interactive_with_monitor_arg(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.pick_port", return_value="/dev/ttyUSB0"), \
             patch("analogdata_esp.commands.build.run_idf_interactive", return_value=0) as mock_run:
            mock_idf.return_value = _fake_cfg(tmp_path)
            runner.invoke(app, ["monitor", "--dir", str(tmp_path)])

        call_args = mock_run.call_args[0][0]
        assert "monitor" in call_args


# ─────────────────────────────────────────────────────────────────────────────
# CLI — menuconfig command
# ─────────────────────────────────────────────────────────────────────────────

class TestMenuconfigCommand:
    def test_help(self):
        result = runner.invoke(app, ["menuconfig", "--help"])
        assert result.exit_code == 0
        assert "menuconfig" in result.output.lower()

    def test_fails_without_idf(self, tmp_path):
        with patch(
            "analogdata_esp.commands.build.detect_idf",
            return_value=IDFConfig(),
        ):
            result = runner.invoke(app, ["menuconfig", "--dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_calls_idf_menuconfig(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.run_idf_interactive", return_value=0) as mock_run:
            mock_idf.return_value = _fake_cfg(tmp_path)
            runner.invoke(app, ["menuconfig", "--dir", str(tmp_path)])

        call_args = mock_run.call_args[0][0]
        assert "menuconfig" in call_args


# ─────────────────────────────────────────────────────────────────────────────
# CLI — flash-monitor command
# ─────────────────────────────────────────────────────────────────────────────

class TestFlashMonitorCommand:
    def test_help(self):
        result = runner.invoke(app, ["flash-monitor", "--help"])
        assert result.exit_code == 0

    def test_calls_flash_and_monitor(self, tmp_path):
        with patch("analogdata_esp.commands.build.detect_idf") as mock_idf, \
             patch("analogdata_esp.commands.build.pick_port", return_value="/dev/ttyUSB0"), \
             patch("analogdata_esp.commands.build.run_idf_interactive", return_value=0) as mock_run:
            mock_idf.return_value = _fake_cfg(tmp_path)
            runner.invoke(app, ["flash-monitor", "--dir", str(tmp_path)])

        call_args = mock_run.call_args[0][0]
        assert "flash" in call_args
        assert "monitor" in call_args


# ─────────────────────────────────────────────────────────────────────────────
# Agent tool — build_project / flash_project
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentBuildTools:
    def test_build_tool_exists(self):
        from analogdata_esp.agent.tools import TOOL_MAP
        assert "build_project" in TOOL_MAP

    def test_flash_tool_exists(self):
        from analogdata_esp.agent.tools import TOOL_MAP
        assert "flash_project" in TOOL_MAP

    def test_monitor_tool_exists(self):
        from analogdata_esp.agent.tools import TOOL_MAP
        assert "monitor_project" in TOOL_MAP

    def test_build_tool_returns_success_message(self, tmp_path):
        from analogdata_esp.agent.tools import TOOL_MAP
        tool = TOOL_MAP["build_project"]

        fake_lines = ["Compiling...", "Project build complete. To flash, run this command."]
        with patch("analogdata_esp.core.idf_runner.run_idf_streaming",
                   return_value=iter(fake_lines)):
            result = tool.execute({"path": str(tmp_path)}, tmp_path)

        assert "✅" in result

    def test_build_tool_returns_failure_message(self, tmp_path):
        from analogdata_esp.agent.tools import TOOL_MAP
        tool = TOOL_MAP["build_project"]

        fake_lines = ["error: undeclared identifier", "[exit code 1]"]
        with patch("analogdata_esp.core.idf_runner.run_idf_streaming",
                   return_value=iter(fake_lines)):
            result = tool.execute({"path": str(tmp_path)}, tmp_path)

        assert "❌" in result

    def test_flash_tool_no_port_returns_error(self, tmp_path):
        from analogdata_esp.agent.tools import TOOL_MAP
        tool = TOOL_MAP["flash_project"]

        with patch("analogdata_esp.core.idf_runner.pick_port", return_value=None):
            result = tool.execute({}, tmp_path)

        assert "❌" in result
        assert "port" in result.lower()

    def test_flash_tool_success(self, tmp_path):
        from analogdata_esp.agent.tools import TOOL_MAP
        tool = TOOL_MAP["flash_project"]

        with patch("analogdata_esp.core.idf_runner.pick_port", return_value="/dev/ttyUSB0"), \
             patch("analogdata_esp.core.idf_runner.run_idf_interactive", return_value=0):
            result = tool.execute({}, tmp_path)

        assert "✅" in result
