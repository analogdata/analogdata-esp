"""
analogdata-esp — CLI for ESP-IDF projects by Analog Data

This is the entry point for the entire CLI tool.
It wires together all sub-commands and opens the interactive shell
when the user types `analogdata-esp` with no arguments.
"""

# Typer wraps Click to build CLIs from plain Python functions.
# It reads function signatures (type hints) and auto-generates CLI args/options.
import typer

# Rich Console is used throughout the app for styled terminal output (colours, panels, etc.)
from rich.console import Console

# ── Import each sub-command function or Typer sub-app ────────────────────────
# Each command lives in its own file under analogdata_esp/commands/
from analogdata_esp.commands.new import new                          # creates a new project
from analogdata_esp.commands.agent import agent_app                  # AI assistant (Typer group)
from analogdata_esp.commands.doctor import doctor_app                # environment health check
from analogdata_esp.commands.config import config_app                # settings management
from analogdata_esp.commands.build import (                          # idf.py wrappers
    build, flash, monitor, flash_monitor, menuconfig
)

# ── Root Typer app — represents `analogdata-esp` itself ──────────────────────
app = typer.Typer(
    name="analogdata-esp",
    help="[bold cyan]Analog Data[/bold cyan] — ESP-IDF CLI for embedded engineers.",
    rich_markup_mode="rich",              # allow [bold], [cyan] etc. in help strings
    no_args_is_help=False,                # don't print help on bare `analogdata-esp` — open shell instead
    pretty_exceptions_show_locals=False,  # hide local variable values in crash output
)

# Shared console for any output needed directly from main.py
console = Console()

# ── Register single-function commands ────────────────────────────────────────
# app.command("name")(fn) registers fn as `analogdata-esp name`.
# The function's docstring becomes its --help text.
app.command("new",           help="Scaffold a new ESP-IDF project.")(new)
app.command("build",         help="Build the ESP-IDF project (idf.py build).")(build)
app.command("flash",         help="Flash firmware to connected ESP32 (idf.py flash).")(flash)
app.command("monitor",       help="Open serial monitor (idf.py monitor).")(monitor)
app.command("flash-monitor", help="Flash then open monitor in one step.")(flash_monitor)
app.command("menuconfig",    help="Open sdkconfig editor (idf.py menuconfig).")(menuconfig)

# ── Register Typer sub-apps (command groups) ─────────────────────────────────
# add_typer mounts a whole sub-app under a named prefix.
# e.g. `analogdata-esp config idf` → config_app handles "idf" sub-command.
app.add_typer(agent_app,  name="agent",  help="AI agent for ESP-IDF (any provider).")
app.add_typer(doctor_app, name="doctor", help="Check ESP-IDF environment health.")
app.add_typer(config_app, name="config", help="Manage ESP-IDF path and AI provider settings.")


# ── Root callback — handles the bare `analogdata-esp` case ───────────────────
# invoke_without_command=True tells Typer to run this function even when no
# sub-command is given (instead of printing help and exiting).
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Analog Data ESP-IDF CLI.

    Run with no arguments to open the interactive shell, or pass a command
    directly:

        analogdata-esp new blink --target esp32s3

        analogdata-esp build

        analogdata-esp flash --port /dev/tty.usbserial-0001

        analogdata-esp monitor

        analogdata-esp agent "why is my task crashing"

        analogdata-esp doctor
    """
    # ctx.invoked_subcommand is None when nothing was typed after `analogdata-esp`
    if ctx.invoked_subcommand is None:
        # Import lazily — shell.py pulls in Rich panels and agent modules that
        # add startup cost; we only pay that cost when the shell is actually opened.
        from analogdata_esp.commands.shell import open_shell
        # Pass the root app so the shell can dispatch typed commands back into it.
        open_shell(app)


# ── Script entry point for development ───────────────────────────────────────
# Allows `python analogdata_esp/main.py` or `python -m analogdata_esp.main`
if __name__ == "__main__":
    app()
