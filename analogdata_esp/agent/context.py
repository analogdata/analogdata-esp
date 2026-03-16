"""
Context collector — reads build errors, sdkconfig target, IDF version
automatically from the current project directory.

This module is called at the start of every agent session and attaches
live project metadata to every LLM query so the AI always knows what
chip you're targeting and whether there are any recent build errors.
"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ProjectContext:
    """All the metadata we can extract from an ESP-IDF project directory."""
    project_name: Optional[str] = None   # from project(...) in CMakeLists.txt
    idf_target: Optional[str] = None     # e.g. "esp32s3" from sdkconfig
    idf_version: Optional[str] = None    # e.g. "v5.5.3" from sdkconfig
    build_error: Optional[str] = None    # last 50 error lines from build logs
    has_build: bool = False              # True if sdkconfig exists (build has run before)

    def as_text(self) -> str:
        """Format the context as a short plain-text block for the LLM prompt.

        Returns an empty string when nothing useful was found, so callers
        can use `if ctx.as_text():` as a presence check.
        """
        lines = []
        if self.project_name:
            lines.append(f"Project: {self.project_name}")
        if self.idf_target:
            lines.append(f"Target chip: {self.idf_target}")
        if self.idf_version:
            lines.append(f"ESP-IDF version: {self.idf_version}")
        return "\n".join(lines) if lines else ""


def collect_context(cwd: Optional[Path] = None) -> ProjectContext:
    """Collect project context from the current working directory.

    Reads three sources:
      1. CMakeLists.txt → project name
      2. sdkconfig → target chip and IDF version (only exists after first build)
      3. build/log/idf_py_stderr_output → last build error lines
    """
    cwd = cwd or Path.cwd()
    ctx = ProjectContext()

    # ── 1. Project name from CMakeLists.txt ──────────────────────────────────
    cmake_file = cwd / "CMakeLists.txt"
    if cmake_file.exists():
        content = cmake_file.read_text()
        # Match the CMake `project(name)` call — group 1 captures the name
        if m := re.search(r'project\((\w+)\)', content):
            ctx.project_name = m.group(1)

    # ── 2. Target chip and IDF version from sdkconfig ────────────────────────
    # sdkconfig is generated the first time idf.py set-target or reconfigure runs
    sdkconfig = cwd / "sdkconfig"
    if sdkconfig.exists():
        ctx.has_build = True   # sdkconfig present means the project has been built before
        content = sdkconfig.read_text()
        # CONFIG_IDF_TARGET="esp32s3"
        if m := re.search(r'^CONFIG_IDF_TARGET="(\w+)"', content, re.MULTILINE):
            ctx.idf_target = m.group(1)
        # CONFIG_IDF_VER="v5.5.3"
        if m := re.search(r'^CONFIG_IDF_VER="([^"]+)"', content, re.MULTILINE):
            ctx.idf_version = m.group(1)

    # ── 3. Build errors from build log ───────────────────────────────────────
    ctx.build_error = _read_build_error(cwd)

    return ctx


def _read_build_error(cwd: Path) -> Optional[str]:
    """Extract the most relevant build error lines from build output.

    Checks two locations:
      - build/log/idf_py_stderr_output  (primary — idf.py writes here)
      - build/*.log                     (fallback — some older IDF versions)
    """
    error_lines = []

    # Primary location: idf.py stderr log written by ESP-IDF's build system
    stderr_log = cwd / "build" / "log" / "idf_py_stderr_output"
    if stderr_log.exists():
        content = stderr_log.read_text(errors="ignore")   # ignore non-UTF-8 bytes
        error_lines = _extract_errors(content)

    # Fallback: scan any *.log files inside build/ (cmake, ninja, etc.)
    if not error_lines:
        for log_file in (cwd / "build").glob("*.log"):
            content = log_file.read_text(errors="ignore")
            error_lines = _extract_errors(content)
            if error_lines:
                break   # stop at the first log that has relevant errors

    if not error_lines:
        return None

    # Return only the last 50 error lines — the most recent errors are the most relevant
    return "\n".join(error_lines[-50:])


def _extract_errors(content: str) -> list[str]:
    """Filter build output to lines that are likely errors or error context."""
    relevant = []
    for line in content.splitlines():
        lower = line.lower()
        # Keep lines that contain classic compiler/CMake/Ninja error keywords
        if any(kw in lower for kw in ["error:", "undefined", "fatal:", "cmake error", "ninja:"]):
            relevant.append(line.strip())
    return relevant
