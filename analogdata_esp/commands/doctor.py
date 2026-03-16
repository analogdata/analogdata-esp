"""
analogdata-esp doctor — check ESP-IDF environment health.
"""

import os           # read environment variables (API keys)
import shutil       # shutil.which() finds binaries on PATH
import subprocess   # run cmake/git --version to show installed versions
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from analogdata_esp.core.config import idf_config, detect_idf

doctor_app = typer.Typer(help="Check ESP-IDF environment health.")
console = Console()

# Known directories where the ESP-IDF tools installer puts toolchain binaries.
# ~/.espressif/tools is the standard path; ~/.espressifforwindsurf is used by
# the Windsurf IDE's managed ESP-IDF installation.
_TOOLS_ROOTS = [
    Path.home() / ".espressif" / "tools",
    Path.home() / ".espressifforwindsurf" / "tools",
]


def _find_toolchain(binary: str) -> Optional[Path]:
    """Locate a toolchain binary (gcc, objdump, etc.) by name.

    ESP-IDF's toolchains are installed under ~/.espressif/tools/ but are NOT
    on PATH unless export.sh has been sourced. This function finds them even
    when they aren't on PATH, so doctor can report them as "installed (not in PATH)".

    Search order:
      1. System PATH (export.sh was sourced — binary is directly accessible)
      2. ~/.espressif/tools/<toolchain-name>/<version>/<toolchain-name>/bin/<binary>
      3. ~/.espressifforwindsurf/... (Windsurf-managed install)

    Args:
        binary: Binary filename to search for (e.g. "xtensa-esp32-elf-gcc").

    Returns:
        Path to the binary if found, None otherwise.
    """
    # 1. Check PATH first — quickest check
    found = shutil.which(binary)
    if found:
        return Path(found)

    # 2. Walk the known tools roots
    #    The directory structure is:
    #      <root>/<toolchain-name>/<version>/<toolchain-name>/bin/<binary>
    #    Example: ~/.espressif/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin/xtensa-esp32-elf-gcc
    prefix = binary.rsplit("-", 1)[0]   # "xtensa-esp32-elf-gcc" → "xtensa-esp32-elf"
    candidates = []
    for root in _TOOLS_ROOTS:
        if not root.exists():
            continue
        for tool_dir in root.iterdir():
            # Only look inside directories whose name is related to the binary we want.
            # We check the dir name itself AND a couple of known toolchain folder names.
            if not any(
                binary.startswith(stem)
                for stem in (tool_dir.name, tool_dir.name.replace("32-", "32s3-"))
            ) and tool_dir.name not in ("xtensa-esp-elf", "riscv32-esp-elf"):
                # Quick prefix check: skip completely unrelated directories
                if not binary.startswith(tool_dir.name.split("-")[0]):
                    continue
            # Walk one level of version directories inside the toolchain folder
            for version_dir in tool_dir.iterdir():
                # The binary lives under <version>/<toolchain-name>/bin/<binary>
                candidate = version_dir / tool_dir.name / "bin" / binary
                if candidate.exists():
                    candidates.append(candidate)

    if candidates:
        return candidates[0]   # return the first match (newest would be better, but first is fine)
    return None


def _toolchain_row(table: Table, label: str, binary: str) -> None:
    """Add a toolchain check row to the doctor table.

    Three possible states:
      ✅ in PATH    — binary is on PATH (export.sh was sourced)
      ✅ installed  — binary found in ~/.espressif/tools but not on PATH
      ❌ not found  — binary not found anywhere — installer needs to be run

    Args:
        table:  Rich Table to add the row to.
        label:  Human-readable label for the row (e.g. "xtensa-esp-elf-gcc").
        binary: Binary filename to search for (e.g. "xtensa-esp32-elf-gcc").
    """
    path = _find_toolchain(binary)
    if path is None:
        # Not installed at all — the user needs to run the ESP-IDF tools installer
        table.add_row(
            label,
            "[red]❌ not found[/red]",
            "Run the ESP-IDF installer",
        )
        return

    # Found — check if it's also on PATH
    in_path = shutil.which(binary) is not None
    if in_path:
        # On PATH — fully usable without any extra setup
        table.add_row(label, "[green]✅ in PATH[/green]", str(path))
    else:
        # Installed but not on PATH — this is normal before sourcing export.sh.
        # analogdata-esp handles this by building the env dict itself (idf_runner.py).
        table.add_row(
            label,
            "[green]✅ installed[/green]",
            f"{path.parent}  [dim](source export.sh to add to PATH)[/dim]",
        )


@doctor_app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """
    Check ESP-IDF installation, tools, and AI agent backends.

    Checks (in order):
      1. ESP-IDF path and version
      2. Python virtualenv
      3. xtensa (ESP32/S2/S3) and riscv32 (C/H/P series) toolchains
      4. cmake and ninja (build tools)
      5. git
      6. Ollama (local AI) — running, which models are pulled
      7. OpenAI / Anthropic / Gemini API keys (from environment variables)
    """
    # If a sub-command was invoked (e.g. `doctor check`) let it handle itself
    if ctx.invoked_subcommand is not None:
        return

    console.print()
    console.print("[bold cyan]⚡ analogdata-esp doctor[/bold cyan]\n")

    # Build a three-column table: Check | Status | Detail
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Check",  style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    # detect_idf() checks saved config first, then auto-detects
    cfg = detect_idf()

    # ── ESP-IDF path ──────────────────────────────────────────────────────────
    if cfg.idf_path and cfg.idf_path.exists():
        table.add_row("ESP-IDF", "[green]✅ found[/green]", str(cfg.idf_path))
    else:
        # Not found — give the user actionable guidance
        table.add_row("ESP-IDF", "[red]❌ not found[/red]", "Run EIM installer or clone manually")

    # ── Version ───────────────────────────────────────────────────────────────
    # Read from esp-idf/version.txt (e.g. "v5.5")
    if cfg.version:
        table.add_row("IDF version", "[green]✅[/green]", cfg.version)
    else:
        table.add_row("IDF version", "[yellow]⚠ unknown[/yellow]", "")

    # ── Python venv ───────────────────────────────────────────────────────────
    # ESP-IDF uses its own Python virtualenv (separate from system Python)
    # so that idf.py dependencies don't conflict with the system
    if cfg.python_path and cfg.python_path.exists():
        table.add_row("Python (venv)", "[green]✅ found[/green]", str(cfg.python_path))
    else:
        table.add_row("Python (venv)", "[yellow]⚠ not found[/yellow]", "Using system Python")

    # ── Toolchains ────────────────────────────────────────────────────────────
    # xtensa-esp-elf-gcc: used for Xtensa-based chips (ESP32, ESP32-S2, ESP32-S3)
    # riscv32-esp-elf-gcc: used for RISC-V chips (ESP32-C2/C3/C6, ESP32-H2, ESP32-P4)
    _toolchain_row(table, "xtensa-esp-elf-gcc",   "xtensa-esp32-elf-gcc")
    _toolchain_row(table, "riscv32-esp-elf-gcc",  "riscv32-esp-elf-gcc")

    # ── Build tools ───────────────────────────────────────────────────────────
    # cmake: ESP-IDF's build system is based on CMake
    cmake = shutil.which("cmake")
    if cmake:
        # Show the cmake version string (first line of `cmake --version`)
        v = subprocess.run(
            ["cmake", "--version"], capture_output=True, text=True
        ).stdout.split("\n")[0]
        table.add_row("cmake", "[green]✅[/green]", v)
    else:
        table.add_row("cmake", "[red]❌ not found[/red]", "brew install cmake")

    # ninja: fast build tool used by ESP-IDF instead of make
    ninja = shutil.which("ninja")
    if ninja:
        table.add_row("ninja", "[green]✅[/green]", ninja)
    else:
        table.add_row("ninja", "[red]❌ not found[/red]", "brew install ninja")

    # git: needed for esp-idf component manager and submodule updates
    git = shutil.which("git")
    if git:
        v = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        ).stdout.strip()
        table.add_row("git", "[green]✅[/green]", v)
    else:
        table.add_row("git", "[red]❌ not found[/red]", "Install Xcode CLI tools")

    # ── Ollama ────────────────────────────────────────────────────────────────
    # Ollama is the local AI backend — no API key needed, runs entirely on-device.
    # We probe its REST API at localhost:11434 (the default port).
    import httpx
    ollama_ok = False
    try:
        # GET /api/tags returns the list of locally pulled models
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            gemma_models = [m for m in models if "gemma" in m]   # preferred model family
            if gemma_models:
                table.add_row(
                    "Ollama + Gemma", "[green]✅ running[/green]", ", ".join(gemma_models)
                )
                ollama_ok = True
            elif models:
                # Ollama is running but no Gemma model — suggest pulling one
                table.add_row(
                    "Ollama", "[yellow]⚠ running, no Gemma[/yellow]",
                    f"Models: {', '.join(models[:3])}  (ollama pull gemma3:4b)",
                )
                ollama_ok = True   # Ollama is up even without Gemma
            else:
                # Ollama is running but no models at all — needs ollama pull
                table.add_row(
                    "Ollama", "[yellow]⚠ running, no models[/yellow]",
                    "Run: ollama pull gemma3:4b",
                )
    except Exception:
        # Connection refused → Ollama isn't running; or network error
        table.add_row("Ollama", "[dim]not running[/dim]", "Install from ollama.com")

    # ── API keys ─────────────────────────────────────────────────────────────
    # Check for cloud AI provider API keys in environment variables.
    # We only show the last 6 chars of each key for security.
    for env_var, label in [
        ("OPENAI_API_KEY",    "OpenAI API key"),
        ("ANTHROPIC_API_KEY", "Anthropic API key"),
        ("GEMINI_API_KEY",    "Gemini API key"),
    ]:
        key = os.environ.get(env_var)
        if key:
            # Show last 6 chars — enough to confirm it's set, not enough to leak it
            table.add_row(label, "[green]✅ set[/green]", f"...{key[-6:]}")
        else:
            # Tailor the hint: if Ollama works, API keys are truly optional
            hint = "Optional (Ollama is available)" if ollama_ok else f"Set to use {label.split()[0]}"
            table.add_row(label, "[dim]not set[/dim]", hint)

    console.print(table)
    console.print()
