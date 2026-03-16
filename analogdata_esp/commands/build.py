"""
analogdata-esp build / flash / monitor — run idf.py without sourcing export.sh.

Commands:
  analogdata-esp build              Build the project in the current directory
  analogdata-esp flash              Flash the built firmware to connected ESP32
  analogdata-esp monitor            Open the serial monitor
  analogdata-esp flash-monitor      Flash then open monitor in one step
"""

from __future__ import annotations

import sys               # sys.platform to show platform-specific port hints
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule      # horizontal divider line

# detect_idf() finds the ESP-IDF installation and returns an IDFConfig object
from analogdata_esp.core.config import detect_idf
# idf_runner helpers: serial port detection, interactive runner, streaming runner
from analogdata_esp.core.idf_runner import (
    detect_serial_ports,
    pick_port,
    run_idf_interactive,
    run_idf_streaming,
)

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_project_root(start: Optional[Path]) -> Path:
    """Find the ESP-IDF project root containing CMakeLists.txt.

    ESP-IDF projects must have a top-level CMakeLists.txt. This function
    searches for it in three ways, in order of likelihood:

      1. The given directory (or cwd) itself — most common case.
      2. Walk UP through parents — user is inside a subdirectory of the project.
      3. Check immediate subdirectories — catches the case where the user
         is in ~/blink but the project is in ~/blink/blink/ (created by 'new').

    Args:
        start: Starting directory. None → use cwd.

    Returns:
        Path to the project root directory (may not have CMakeLists.txt
        if none was found — idf.py will show its own error in that case).
    """
    here = (start or Path.cwd()).resolve()

    # Walk up first — most common case: user is already inside the project
    for candidate in [here, *here.parents]:
        if (candidate / "CMakeLists.txt").exists():
            return candidate

    # Check immediate subdirectories — e.g. user ran 'new blink' from ~/blink,
    # so the project is at ~/blink/blink/CMakeLists.txt
    try:
        for sub in sorted(d for d in here.iterdir() if d.is_dir() and not d.name.startswith(".")):
            if (sub / "CMakeLists.txt").exists():
                console.print(
                    f"[dim]Project found in:[/dim] [cyan]{sub.name}/[/cyan]"
                )
                return sub
    except PermissionError:
        pass   # can't list directory — fall back to cwd

    return here  # fall back to cwd — idf.py will show its own error


def _require_idf() -> None:
    """Check that ESP-IDF is configured; print an error and exit if not.

    Called at the start of every build/flash/monitor command.
    If idf_config.is_valid is False (no IDF path found), the command
    cannot proceed and should guide the user to configure it.
    """
    cfg = detect_idf()
    if not cfg.is_valid:
        console.print(
            "[red]❌  ESP-IDF not found.[/red]  "
            "Run [cyan]analogdata-esp config idf[/cyan] to set the path."
        )
        raise typer.Exit(1)   # non-zero exit code signals failure to shell callers


def _show_ports_hint() -> None:
    """Show which serial ports were detected and how to pick one explicitly.

    Called when no port is found or multiple ports exist so the user
    knows what they should pass to --port.
    """
    ports = detect_serial_ports()
    if ports:
        console.print(f"[dim]Detected serial ports: {', '.join(ports)}[/dim]")
        console.print(
            "[dim]Use [cyan]--port <port>[/cyan] to select one explicitly.[/dim]"
        )
    else:
        # Platform-specific hint message
        if sys.platform == "darwin":
            console.print("[dim]No USB serial ports detected. Connect your ESP32.[/dim]")
        else:
            console.print("[dim]No serial ports detected. Connect your ESP32.[/dim]")


def _resolve_port(port: Optional[str], require: bool = True) -> Optional[str]:
    """Resolve the serial port: use explicit value, or auto-detect.

    If the user passed --port explicitly, use that.
    Otherwise, try to auto-detect from USB serial devices.
    If require=True and no port found, print an error and exit.

    Args:
        port:    User-supplied port string, or None for auto-detect.
        require: If True, raise Exit(1) when no port can be found.

    Returns:
        Resolved port string (e.g. "/dev/tty.usbserial-0001"), or None.
    """
    resolved = pick_port(port)   # pick_port returns override if given, else first detected
    if resolved:
        console.print(f"[dim]Using port: [cyan]{resolved}[/cyan][/dim]")
        return resolved
    if require:
        _show_ports_hint()   # tell user what was found (or nothing)
        console.print("[red]❌  No serial port found.[/red]  Pass [cyan]--port /dev/ttyUSBx[/cyan]")
        raise typer.Exit(1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# build
# ─────────────────────────────────────────────────────────────────────────────

def build(
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory (walks up for CMakeLists.txt).",
    ),
    target: Optional[str] = typer.Option(
        None, "--target", "-t",
        help="Override IDF_TARGET (e.g. esp32s3). Usually set in CMakeLists.txt.",
    ),
    jobs: int = typer.Option(
        0, "--jobs", "-j",
        help="Parallel build jobs. 0 = auto.",
    ),
) -> None:
    """
    Build an ESP-IDF project (runs idf.py build).

    Automatically sets up ESP-IDF environment — no need to source export.sh.

    Examples:

        analogdata-esp build

        analogdata-esp build --dir ~/esp/blink

        analogdata-esp build -j 8
    """
    # Guard: ESP-IDF must be configured before we can build
    _require_idf()
    # Find the directory containing CMakeLists.txt
    project_dir = _find_project_root(dir)

    console.print()
    console.print(f"[bold cyan]⚡ Building[/bold cyan]  [dim]{project_dir}[/dim]")
    console.print(Rule(style="dim"))   # visual separator before compiler output

    # Build the idf.py argument list
    args = ["build"]
    if target:
        # --define-cache-vars overrides IDF_TARGET without editing CMakeLists.txt
        args = ["--define-cache-vars", f"IDF_TARGET={target}"] + args
    if jobs > 0:
        # -j8 tells ninja (the underlying build tool) to run 8 jobs in parallel
        args += [f"-j{jobs}"]

    ok = True   # track whether build succeeded (no exit code error line seen)
    # run_idf_streaming() yields output lines as the compiler runs — real-time output
    for line in run_idf_streaming(args, cwd=project_dir):
        # Colour-code important line types so errors are immediately visible
        if "error:" in line.lower() or "error]" in line.lower():
            console.print(f"[red]{line}[/red]")
        elif "warning:" in line.lower():
            console.print(f"[yellow]{line}[/yellow]")
        elif line.startswith("[exit code"):
            # run_idf_streaming() appends "[exit code N]" on non-zero exit
            ok = False
            console.print(f"[red]{line}[/red]")
        else:
            console.print(line)   # normal build progress lines

    console.print(Rule(style="dim"))   # visual separator after compiler output
    if ok:
        console.print("[bold green]✅  Build successful.[/bold green]")
        console.print(
            f"[dim]Flash with:[/dim]  [cyan]analogdata-esp flash[/cyan]"
        )
    else:
        console.print("[bold red]❌  Build failed.[/bold red]")
        # Suggest using the agent to explain the error
        console.print(
            "[dim]Ask the agent:[/dim]  [cyan]analogdata-esp agent \"explain my build error\"[/cyan]"
        )
        raise typer.Exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# flash
# ─────────────────────────────────────────────────────────────────────────────

def flash(
    port: Optional[str] = typer.Option(
        None, "--port", "-p",
        help="Serial port (e.g. /dev/tty.usbserial-0001). Auto-detected if omitted.",
    ),
    baud: int = typer.Option(
        460800, "--baud", "-b",
        help="Flash baud rate.",
    ),
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory.",
    ),
    no_build: bool = typer.Option(
        False, "--no-build",
        help="Skip automatic build before flash.",
    ),
) -> None:
    """
    Flash firmware to a connected ESP32 (runs idf.py flash).

    Auto-detects the serial port. Builds first unless --no-build is passed.

    Examples:

        analogdata-esp flash

        analogdata-esp flash --port /dev/tty.usbserial-0001

        analogdata-esp flash --baud 921600
    """
    _require_idf()
    project_dir   = _find_project_root(dir)
    resolved_port = _resolve_port(port, require=True)   # exits if no port found

    console.print()
    console.print(
        f"[bold cyan]⚡ Flashing[/bold cyan]  [dim]{project_dir}[/dim]  "
        f"→ [cyan]{resolved_port}[/cyan]"
    )
    console.print(Rule(style="dim"))

    # Build the idf.py argument list: -p <port> -b <baud> flash [--no-build]
    args = ["-p", resolved_port, "-b", str(baud), "flash"]
    if no_build:
        args.append("--no-build")   # idf.py flash --no-build skips the build step

    # run_idf_interactive() inherits the terminal so esptool progress bars display properly
    rc = run_idf_interactive(args, cwd=project_dir)
    console.print(Rule(style="dim"))

    if rc == 0:
        console.print("[bold green]✅  Flash successful.[/bold green]")
        # Suggest opening the monitor right after flashing
        console.print(
            f"[dim]Open monitor:[/dim]  [cyan]analogdata-esp monitor --port {resolved_port}[/cyan]"
        )
    else:
        console.print(f"[bold red]❌  Flash failed (exit {rc}).[/bold red]")
        raise typer.Exit(rc)   # propagate the non-zero exit code


# ─────────────────────────────────────────────────────────────────────────────
# monitor
# ─────────────────────────────────────────────────────────────────────────────

def monitor(
    port: Optional[str] = typer.Option(
        None, "--port", "-p",
        help="Serial port. Auto-detected if omitted.",
    ),
    baud: Optional[int] = typer.Option(
        None, "--baud", "-b",
        help="Monitor baud rate. Defaults to value in sdkconfig.",
    ),
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory.",
    ),
) -> None:
    """
    Open the serial monitor for a connected ESP32 (runs idf.py monitor).

    Press Ctrl+] to exit the monitor.

    Examples:

        analogdata-esp monitor

        analogdata-esp monitor --port /dev/tty.usbserial-0001

        analogdata-esp monitor --baud 115200
    """
    _require_idf()
    project_dir   = _find_project_root(dir)
    resolved_port = _resolve_port(port, require=True)

    console.print()
    console.print(
        f"[bold cyan]⚡ Monitor[/bold cyan]  [dim]{project_dir}[/dim]  "
        f"→ [cyan]{resolved_port}[/cyan]"
    )
    # Remind the user how to exit — Ctrl+] is non-obvious
    console.print("[dim]Press [bold]Ctrl+][/bold] to exit.[/dim]")
    console.print(Rule(style="dim"))

    # Build args: -p <port> monitor [-b <baud>]
    args = ["-p", resolved_port, "monitor"]
    if baud:
        args += ["-b", str(baud)]   # override baud rate if specified

    rc = run_idf_interactive(args, cwd=project_dir)
    # Exit code 130 = SIGINT (Ctrl+C) — normal exit for a terminal program
    if rc not in (0, 130):
        console.print(f"[yellow]Monitor exited with code {rc}.[/yellow]")


# ─────────────────────────────────────────────────────────────────────────────
# flash-monitor  (combined)
# ─────────────────────────────────────────────────────────────────────────────

def flash_monitor(
    port: Optional[str] = typer.Option(
        None, "--port", "-p",
        help="Serial port. Auto-detected if omitted.",
    ),
    baud: int = typer.Option(
        460800, "--baud", "-b",
        help="Flash baud rate.",
    ),
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory.",
    ),
) -> None:
    """
    Flash firmware then immediately open the serial monitor.

    Equivalent to `idf.py flash monitor`. Press Ctrl+] to exit monitor.

    Examples:

        analogdata-esp flash-monitor

        analogdata-esp flash-monitor --port /dev/tty.usbserial-0001
    """
    _require_idf()
    project_dir   = _find_project_root(dir)
    resolved_port = _resolve_port(port, require=True)

    console.print()
    console.print(
        f"[bold cyan]⚡ Flash → Monitor[/bold cyan]  [dim]{project_dir}[/dim]  "
        f"→ [cyan]{resolved_port}[/cyan]"
    )
    console.print("[dim]Press [bold]Ctrl+][/bold] to exit monitor.[/dim]")
    console.print(Rule(style="dim"))

    # Passing "flash" and "monitor" together tells idf.py to do both in sequence
    args = ["-p", resolved_port, "-b", str(baud), "flash", "monitor"]
    rc = run_idf_interactive(args, cwd=project_dir)
    if rc not in (0, 130):   # 130 = Ctrl+C — normal monitor exit
        console.print(f"[yellow]Exited with code {rc}.[/yellow]")


# ─────────────────────────────────────────────────────────────────────────────
# menuconfig
# ─────────────────────────────────────────────────────────────────────────────

def menuconfig(
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory.",
    ),
) -> None:
    """
    Open the interactive sdkconfig editor (runs idf.py menuconfig).

    Use arrow keys to navigate, Space/Enter to toggle, S to save, Q to quit.
    Changes are written to sdkconfig and sdkconfig.old in the project root.

    Examples:

        analogdata-esp menuconfig

        analogdata-esp menuconfig --dir ~/esp/blink
    """
    _require_idf()
    project_dir = _find_project_root(dir)

    console.print()
    console.print(
        f"[bold cyan]⚡ menuconfig[/bold cyan]  [dim]{project_dir}[/dim]"
    )
    # Navigation hint — menuconfig uses ncurses keyboard shortcuts
    console.print(
        "[dim]Navigate with arrows · Space/Enter to toggle · "
        "[bold]S[/bold] to save · [bold]Q[/bold] to quit[/dim]"
    )
    console.print(Rule(style="dim"))

    # menuconfig is a full terminal UI (ncurses) — must use interactive runner
    rc = run_idf_interactive(["menuconfig"], cwd=project_dir)
    if rc not in (0, 130):
        console.print(f"[yellow]menuconfig exited with code {rc}.[/yellow]")
