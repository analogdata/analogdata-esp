"""
Template engine — copies and renders ESP-IDF project templates.
"""

import json        # write .vscode/settings.json
import shutil      # shutil.copytree() copies the template directory recursively
import subprocess  # run git init / git commit, and idf.py set-target
from pathlib import Path
from typing import Optional

# Jinja2: the template engine used to replace {{ project_name }} etc. in template files
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

# get_template_dir(): finds bundled templates (handles PyInstaller + dev installs)
# idf_config: module-level singleton with detected IDF paths
from analogdata_esp.core.config import get_template_dir, idf_config

console = Console()

# All chip targets supported by ESP-IDF v5.x
# Used for validation in the `new` command and as IntelliSense hints
SUPPORTED_TARGETS = [
    "esp32", "esp32s2", "esp32s3",
    "esp32c2", "esp32c3", "esp32c6",
    "esp32h2", "esp32p4",
]


def scaffold_project(
    name: str,
    target: str,
    output_dir: Path,
    git_init: bool = True,
) -> Path:
    """Scaffold a new ESP-IDF project from the bundled template.

    Steps:
      1. Copy the esp32-default template directory to output_dir/name.
      2. Render Jinja2 placeholders ({{ project_name }}, {{ target }}, etc.)
         in all template files.
      3. Optionally run `git init && git add . && git commit`.
      4. Run `idf.py set-target <target>` + `idf.py reconfigure` to create
         the build directory and sdkconfig for the correct chip.

    Args:
        name:       Project name (already normalised — underscores, no spaces).
        target:     ESP chip target string, e.g. "esp32s3".
        output_dir: Parent directory; project will be created at output_dir/name.
        git_init:   Whether to initialise a git repository.

    Returns:
        Path to the created project directory.

    Raises:
        FileExistsError:  If output_dir/name already exists.
        FileNotFoundError: If the template directory is missing.
    """
    project_dir = output_dir / name

    # Refuse to overwrite an existing project directory
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    # The bundled template lives at templates/esp32-default/
    template_src = get_template_dir() / "esp32-default"
    if not template_src.exists():
        raise FileNotFoundError(f"Template not found: {template_src}")

    # Copy the entire template tree to the new project location
    shutil.copytree(template_src, project_dir)

    # Build a dict of values to substitute into Jinja2 placeholders
    # Includes project name, target chip, and live IDF/Python paths
    context = _build_render_context(name, target)

    # Walk all text files in the project and replace {{ variable }} tokens
    _render_template(project_dir, context)

    # Set up git repository (optional — useful for version control from day one)
    if git_init:
        _git_init(project_dir)

    # Run idf.py set-target to configure the project for the correct chip.
    # This creates build/CMakeCache.txt and generates the initial sdkconfig.
    if idf_config.is_valid:
        _run_idf_setup(project_dir, target)
    else:
        # IDF not found — project files were created but not configured for the chip
        console.print("[yellow]⚠  ESP-IDF not found — skipping set-target and reconfigure.[/yellow]")
        console.print("[dim]Run 'analogdata-esp doctor' to diagnose.[/dim]")

    return project_dir


def write_vscode_settings(project_dir: Path, target: Optional[str] = None) -> None:
    """Write (or overwrite) .vscode/settings.json with correct ESP-IDF extension paths.

    The official ESP-IDF VS Code extension requires specific keys in settings.json
    to know where to find the IDF framework, tools, and Python. Without these,
    the extension shows "command not found" errors for build/flash/monitor actions.

    This function is called:
      - During `new` (via scaffold_project) to set up the project correctly.
      - Standalone via `analogdata-esp config vscode` to fix an existing project.

    Key settings written:
      idf.espIdfPath       — path to esp-idf directory
      idf.toolsPath        — path to ~/.espressif (tools root)
      idf.pythonBinPath    — path to the IDF virtualenv Python binary
      idf.adapterTargetName — chip target for OpenOCD (e.g. "esp32s3")

    Args:
        project_dir: Root directory of the ESP-IDF project (contains CMakeLists.txt).
        target:      Target chip string. None → read from sdkconfig (defaults to "esp32").
    """
    # Ensure .vscode/ directory exists (create if needed)
    vscode_dir = project_dir / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    # Auto-detect target from sdkconfig if not passed explicitly
    if target is None:
        sdkconfig = project_dir / "sdkconfig"
        if sdkconfig.exists():
            import re
            # sdkconfig line format: CONFIG_IDF_TARGET="esp32s3"
            m = re.search(r'^CONFIG_IDF_TARGET="(\w+)"', sdkconfig.read_text(), re.MULTILINE)
            target = m.group(1) if m else "esp32"
        else:
            target = "esp32"   # safe default before first build

    # Build the context dict with live IDF paths
    ctx = _build_render_context(project_dir.name, target)

    settings = {
        # ── ESP-IDF Extension ──────────────────────────────────────────────
        # These three keys are required by the official ESP-IDF VS Code extension.
        # Without them the extension can't find idf.py, the toolchain, or Python.
        "idf.espIdfPath":       ctx["idf_path"],    # path to esp-idf directory
        "idf.toolsPath":        ctx["tools_path"],   # path to ~/.espressif
        "idf.pythonBinPath":    ctx["python_bin"],   # path to venv Python binary
        "idf.adapterTargetName": target,             # chip: esp32, esp32s3, etc.
        "idf.openOcdConfigs":   [f"target/{target}.cfg"],   # OpenOCD config for the chip

        # ── CMake Tools: disable ───────────────────────────────────────────
        # The CMake Tools extension would try to configure the project with its own
        # settings and conflict with ESP-IDF's CMake-based build system.
        # We disable all auto-configuration to prevent "kit scan" popups.
        "cmake.configureOnOpen":        False,
        "cmake.autoSelectActiveFolder": False,
        "cmake.enableAutomaticKitScan": False,
        "cmake.automaticReconfigure":   False,

        # ── C/C++ IntelliSense ─────────────────────────────────────────────
        # Point IntelliSense at ESP-IDF's compile_commands.json so it knows
        # all include paths and macros used during the actual build.
        # This is what enables accurate code completion for ESP-IDF APIs.
        "C_Cpp.intelliSenseEngine":         "default",
        "C_Cpp.default.compileCommands":    "${workspaceFolder}/build/compile_commands.json",
        "C_Cpp.errorSquiggles":             "enabled",

        # ── Editor: embedded-friendly ─────────────────────────────────────
        # 4-space indentation is the ESP-IDF coding standard.
        # Rulers at column 100 match the ESP-IDF line length convention.
        # formatOnSave disabled because clang-format needs manual configuration.
        "editor.tabSize":              4,
        "editor.insertSpaces":         True,
        "editor.detectIndentation":    False,
        "editor.rulers":               [100],
        "editor.formatOnSave":         False,

        # ── File excludes ─────────────────────────────────────────────────
        # .git and .cache are hidden in the file explorer.
        # build/ is kept visible (False) so the user can inspect build artifacts.
        "files.exclude": {
            "**/.git":    True,
            "**/build":   False,
            "**/.cache":  True,
        },
        # Associate ESP-IDF-specific file types with their correct language mode
        "files.associations": {
            "*.h":              "c",           # header files → C language mode
            "sdkconfig":        "properties",  # sdkconfig is a key=value format
            "sdkconfig.old":    "properties",
            "CMakeLists.txt":   "cmake",
        },

        # ── Search excludes ───────────────────────────────────────────────
        # Exclude large/generated directories from VS Code's search (Ctrl+Shift+F).
        # build/ can contain thousands of generated files; managed_components has
        # downloaded component source code — neither are useful to search.
        "search.exclude": {
            "**/build":                True,
            "**/.cache":               True,
            "**/managed_components":   True,
        },
    }

    # Write settings.json with 2-space indentation (standard JSON style)
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _build_render_context(name: str, target: str) -> dict:
    """Build the variable substitution context for Jinja2 templates and settings.json.

    Reads live IDF paths from the module-level idf_config singleton.
    The python_bin key requires extra logic: the VS Code ESP-IDF extension
    expects the python_env/ virtualenv python, not the tools/python/ venv python.

    Args:
        name:   Project name string.
        target: Chip target string (e.g. "esp32s3").

    Returns:
        Dict with keys: project_name, target, idf_path, tools_path, python_bin.
    """
    cfg = idf_config

    # IDF path: e.g. ~/.espressif/idf/v5.5/esp-idf
    idf_path   = str(cfg.idf_path)   if cfg.idf_path   else ""
    # tools_root is the parent of tools/ — e.g. ~/.espressif (not ~/.espressif/tools)
    tools_root = str(cfg.tools_path.parent) if cfg.tools_path else ""

    # VS Code ESP-IDF extension expects the python_env virtualenv, not the tools venv.
    # Try ~/.espressif/python_env/<newest env>/bin/python3 first.
    python_bin = ""
    if cfg.tools_path:
        py_env_root = cfg.tools_path.parent / "python_env"   # ~/.espressif/python_env/
        if py_env_root.is_dir():
            # sorted(..., reverse=True) → newest virtualenv directory first
            for env_dir in sorted(py_env_root.iterdir(), reverse=True):
                candidate = env_dir / "bin" / "python3"
                if candidate.exists():
                    python_bin = str(candidate)
                    break
    # Fallback: use the tools Python we already detected in cfg
    if not python_bin and cfg.python_path and cfg.python_path.exists():
        python_bin = str(cfg.python_path)

    return {
        "project_name": name,
        "target":       target,
        "idf_path":     idf_path,
        "tools_path":   tools_root,
        "python_bin":   python_bin,
    }


def _render_template(project_dir: Path, context: dict) -> None:
    """Render Jinja2 {{ variable }} placeholders in all template files.

    Walks every file in the project directory and replaces {{ tokens }}
    using the provided context dict. Only processes text-based file types
    to avoid corrupting binary files (images, compiled objects, etc.).

    Args:
        project_dir: Root directory of the newly scaffolded project.
        context:     Dict of values to substitute (project_name, target, etc.).
    """
    # Jinja2 Environment: FileSystemLoader makes the project directory the template root
    env = Environment(loader=FileSystemLoader(str(project_dir)))

    # Only process text file types that may contain {{ ... }} placeholders
    renderable_extensions = {".c", ".cpp", ".h", ".txt", ".md", ".json", ".yaml", ".yml"}

    for file_path in project_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in renderable_extensions:
            try:
                content = file_path.read_text(encoding="utf-8")
                if "{{" in content:
                    # Path must be relative so Jinja2 can load it from the FileSystemLoader
                    relative = file_path.relative_to(project_dir)
                    template = env.get_template(str(relative))
                    # Render substitutes all {{ variable }} occurrences
                    rendered = template.render(**context)
                    file_path.write_text(rendered, encoding="utf-8")
            except Exception:
                pass  # skip binary or unrenderable files silently


def _git_init(project_dir: Path) -> None:
    """Initialise a git repository in the project directory and make an initial commit.

    capture_output=True suppresses git's stdout/stderr (we don't want it mixed
    into the `new` command's progress output).
    check=True raises CalledProcessError if git exits non-zero.

    Args:
        project_dir: Directory where git init should be run.
    """
    try:
        subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit — analogdata-esp scaffold"],
            cwd=project_dir, capture_output=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # git not installed or git commit failed (e.g. no user.email configured)
        # Not fatal — the project is still usable without git
        console.print("[yellow]⚠  git not found — skipping git init.[/yellow]")


def _run_idf_setup(project_dir: Path, target: str) -> None:
    """Run `idf.py set-target <target>` and `idf.py reconfigure` in the project.

    set-target:  Writes the chip name into sdkconfig and CMakeCache.txt.
                 Required before building — without it, the wrong chip headers
                 would be used and the firmware would not run on the device.

    reconfigure: Runs CMake to regenerate build files for the target chip.
                 Also creates compile_commands.json which IntelliSense needs.

    capture_output=True hides the (verbose) output — the `new` command's
    Progress spinner is already showing. Errors are truncated to 200 chars.

    Args:
        project_dir: Project directory (already created by shutil.copytree).
        target:      Chip target string (e.g. "esp32s3").
    """
    idf_py = idf_config.idf_path / "tools" / "idf.py"
    python  = str(idf_config.python_path)   # use the IDF venv Python
    env     = _build_idf_env()              # minimal env with IDF_PATH set

    try:
        # set-target writes CONFIG_IDF_TARGET to sdkconfig and reruns CMake for the chip
        subprocess.run(
            [python, str(idf_py), "set-target", target],
            cwd=project_dir, env=env, check=True, capture_output=True
        )
        # reconfigure regenerates CMake build files without a full rebuild
        subprocess.run(
            [python, str(idf_py), "reconfigure"],
            cwd=project_dir, env=env, check=True, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        # Decode bytes error output, truncate to avoid flooding the terminal
        console.print(f"[yellow]⚠  idf.py setup failed: {e.stderr.decode()[:200]}[/yellow]")


def _build_idf_env() -> dict:
    """Build a minimal environment dict for running idf.py during scaffolding.

    This is a lighter version of idf_runner.build_idf_env() — it only sets
    IDF_PATH and IDF_TOOLS_PATH, which is enough for set-target and reconfigure.
    The full build environment (with all toolchain bin/ dirs on PATH) is only
    needed when actually compiling code.

    Returns:
        Copy of os.environ with IDF_PATH and IDF_TOOLS_PATH added.
    """
    import os
    env = os.environ.copy()   # don't mutate the real environment
    cfg = idf_config
    if cfg.idf_path:
        env["IDF_PATH"] = str(cfg.idf_path)
    if cfg.tools_path:
        # IDF_TOOLS_PATH is the parent of tools/ (e.g. ~/.espressif, not ~/.espressif/tools)
        env["IDF_TOOLS_PATH"] = str(cfg.tools_path)
    return env
