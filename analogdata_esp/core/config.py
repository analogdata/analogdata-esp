"""
Core configuration — detects ESP-IDF paths for Mac/Windows/Linux.
"""

import os       # read IDF_PATH environment variable
import sys      # sys.platform for Windows-specific paths; sys._MEIPASS for PyInstaller
import shutil   # shutil.which() to find system Python
from pathlib import Path
from dataclasses import dataclass    # @dataclass: auto-generates __init__, __repr__, etc.
from typing import Optional

# Expand ~ to the user's actual home directory once at module load time
HOME = Path.home()


@dataclass
class IDFConfig:
    """Holds all the path information needed to run idf.py.

    Fields:
        idf_path:    Path to the esp-idf directory (contains tools/idf.py).
        tools_path:  Path to ~/.espressif/tools (toolchain binaries).
        python_path: Path to the ESP-IDF venv Python binary.
        version:     IDF version string (e.g. "v5.5" or "unknown").
        is_valid:    True only if idf_path and python_path both exist.
    """
    idf_path:    Optional[Path] = None
    tools_path:  Optional[Path] = None
    python_path: Optional[Path] = None
    version:     Optional[str]  = None
    is_valid:    bool           = False

    def __post_init__(self):
        """Automatically compute is_valid after dataclass __init__ sets the fields.

        is_valid requires BOTH idf_path and python_path to exist on disk.
        This is checked after every construction so callers can always trust
        cfg.is_valid without re-computing it.
        """
        self.is_valid = bool(
            self.idf_path and self.idf_path.exists() and
            self.python_path and self.python_path.exists()
        )


def detect_all_idf() -> list:
    """Return ALL valid ESP-IDF installations found on this machine.

    Searches in priority order:
      1. $IDF_PATH environment variable (user explicitly set it)
      2. ~/.espressifforwindsurf/v*/esp-idf (Windsurf IDE managed install)
      3. ~/.espressif/idf/v*/esp-idf (EIM — Espressif IDE Manager standard path)
      4. ~/esp/esp-idf (the manual clone path from Espressif docs)
      5. C:/Espressif/frameworks/esp-idf-v5* (Windows EIM default)

    Returns:
        List of IDFConfig objects, one per valid installation found.
        Empty list if nothing is installed.
    """
    candidates = []

    # 1. Environment variable (highest priority — user knows exactly what they want)
    if env_path := os.environ.get("IDF_PATH"):
        candidates.append(Path(env_path))

    # 2. Windsurf-specific path — Windsurf IDE's managed ESP-IDF install
    #    sorted(..., reverse=True) → newest version first
    for d in sorted((HOME / ".espressifforwindsurf").glob("v*/esp-idf"), reverse=True):
        candidates.append(d)

    # 3. EIM standard paths — Espressif IDE Manager installs here
    for d in sorted((HOME / ".espressif" / "idf").glob("v*/esp-idf"), reverse=True):
        candidates.append(d)

    # 4. Manual clone path documented in Espressif's "Get Started" guide
    candidates.append(HOME / "esp" / "esp-idf")

    # 5. Windows EIM default install location
    if sys.platform == "win32":
        for d in Path("C:/Espressif/frameworks").glob("esp-idf-v5*"):
            candidates.append(d)

    results = []
    seen = set()   # avoid adding the same path twice
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        # Validate: directory must exist AND have the ESP-IDF CMake project file
        if c.exists() and (c / "tools" / "cmake" / "project.cmake").exists():
            tools_path  = HOME / ".espressif" / "tools"
            python_path = _find_python(tools_path)
            version     = _read_version(c)
            cfg = IDFConfig(
                idf_path=c,
                tools_path=tools_path,
                python_path=python_path,
                version=version,
            )
            results.append(cfg)
    return results


def detect_idf() -> IDFConfig:
    """Detect ESP-IDF installation — saved config first, then auto-detect.

    Priority:
      1. Path saved in ~/.config/analogdata-esp/config.toml (by `config idf`)
      2. Auto-detection via detect_all_idf() (env var, EIM, manual clone)

    Returns:
        IDFConfig for the best installation found, or an empty (invalid) IDFConfig.
    """
    # Check saved config first — user may have explicitly set a non-standard path
    try:
        from analogdata_esp.core.settings import get_idf_setting
        saved_path = get_idf_setting("path")
        if saved_path:
            p = Path(saved_path)
            # Validate: the saved path must still exist and be a real ESP-IDF install
            if p.exists() and (p / "tools" / "cmake" / "project.cmake").exists():
                tools_path = HOME / ".espressif" / "tools"
                # Use saved tools_path if available (user may have a non-standard location)
                saved_tools = get_idf_setting("tools_path")
                if saved_tools:
                    tools_path = Path(saved_tools)
                python_path = _find_python(tools_path)
                version     = _read_version(p)
                return IDFConfig(
                    idf_path=p,
                    tools_path=tools_path,
                    python_path=python_path,
                    version=version,
                )
    except Exception:
        pass   # settings file missing or malformed — fall through to auto-detect

    # Auto-detect all installations and use the first (highest-priority) one
    all_idf = detect_all_idf()
    return all_idf[0] if all_idf else IDFConfig()   # IDFConfig() → is_valid=False


def _find_python(tools_path: Path) -> Optional[Path]:
    """Find the Python binary inside the ESP-IDF virtualenv.

    ESP-IDF creates a Python virtualenv during installation to isolate
    its dependencies (esptool, pyserial, etc.) from the system Python.

    Search order:
      1. ~/.espressif/tools/python/v*/venv/bin/python3 (Linux/macOS)
      2. ~/.espressif/tools/python/v*/venv/Scripts/python.exe (Windows)
      3. System python3 / python (fallback if venv not found)

    Args:
        tools_path: Path to the ESP-IDF tools directory (~/.espressif/tools).

    Returns:
        Path to the Python binary, or system python3 as fallback.
    """
    # sorted(..., reverse=True) → newest virtualenv version first
    for p in sorted(tools_path.glob("python/v*/venv/bin/python3"), reverse=True):
        if p.exists():
            return p
    # Windows uses Scripts/python.exe instead of bin/python3
    for p in sorted(tools_path.glob("python/v*/venv/Scripts/python.exe"), reverse=True):
        if p.exists():
            return p
    # Fallback: use whatever Python is on the system PATH
    return Path(shutil.which("python3") or shutil.which("python") or "python3")


def _read_version(idf_path: Path) -> Optional[str]:
    """Read the IDF version string from version.txt or version.cmake.

    ESP-IDF stores the version in two places depending on how it was installed:
      - version.txt: plain text file, e.g. "v5.5" (present in most installs)
      - tools/cmake/version.cmake: defines IDF_VERSION_MAJOR etc. (older installs)

    Args:
        idf_path: Path to the esp-idf directory.

    Returns:
        Version string (e.g. "v5.5") or "unknown" if neither file found.
    """
    version_file = idf_path / "version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    # Fallback: parse version.cmake for major version hint
    cmake_file = idf_path / "tools" / "cmake" / "version.cmake"
    if cmake_file.exists():
        for line in cmake_file.read_text().splitlines():
            if "IDF_VERSION_MAJOR" in line:
                return "5.x"   # approximate version rather than failing entirely
    return "unknown"


def get_template_dir() -> Path:
    """Return the path to the bundled templates directory.

    Handles three different runtime environments:
      1. PyInstaller frozen binary: data files are extracted to sys._MEIPASS
         alongside the _internal/ directory.
      2. Package install (pip install): templates/ is inside the analogdata_esp package.
      3. Editable/dev install: templates/ sits at the repository root,
         beside the analogdata_esp/ package directory.

    Returns:
        Path to the templates directory (may not exist if distribution is broken).
    """
    # PyInstaller sets sys.frozen=True and sys._MEIPASS to the extraction directory
    # All --add-data files end up there during the build phase
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "templates"

    # __file__ = .../analogdata_esp/core/config.py → navigate up to find templates/
    core_dir  = Path(__file__).parent   # analogdata_esp/core/
    pkg_dir   = core_dir.parent         # analogdata_esp/
    repo_root = pkg_dir.parent          # repository root (where pyproject.toml lives)

    # 1. Inside the package — wheel installs copy templates/ into the package
    if (pkg_dir / "templates").exists():
        return pkg_dir / "templates"
    # 2. Repo root — editable installs keep the original directory layout
    if (repo_root / "templates").exists():
        return repo_root / "templates"
    # Last resort — return expected path even if it doesn't exist yet
    return repo_root / "templates"


# ── Module-level singleton ─────────────────────────────────────────────────
# Computed once at import time and reused everywhere in the codebase.
# Avoids repeatedly scanning the filesystem on every command invocation.
idf_config = detect_idf()
