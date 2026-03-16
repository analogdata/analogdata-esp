"""Interactive config command for analogdata-esp.

Sub-commands:
  config          — show current settings (IDF path, AI provider, API key)
  config idf      — detect and save the ESP-IDF installation path
  config ai       — choose provider (ollama/openai/anthropic/gemini) and model
  config vscode   — write .vscode/settings.json for the current project
  config reset    — delete the config file and start fresh
"""
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Settings functions all read/write ~/.config/analogdata-esp/config.toml
from analogdata_esp.core.settings import (
    CONFIG_FILE,
    load_settings,
    save_settings,
    get_idf_setting,
    set_idf_setting,
    get_ai_setting,
    set_ai_setting,
)
# detect_all_idf scans known install locations and returns a list of IDFConfig objects
from analogdata_esp.core.config import detect_all_idf, IDFConfig

console = Console()
# Sub-app registered as `analogdata-esp config` in main.py
config_app = typer.Typer(help="Manage analogdata-esp configuration.")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mask_key(key: str) -> str:
    """Return a partially-masked API key string safe to display on screen.

    Full key is never shown — shows first/last 4 chars with stars in between.
    """
    if not key:
        return "[dim](not set)[/dim]"
    if len(key) <= 8:
        return "*" * len(key)   # short key → fully mask it
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _validate_idf_path(path_str: str) -> Optional[Path]:
    """Return a resolved Path if the string points to a valid ESP-IDF directory.

    Validation: the directory must contain tools/cmake/project.cmake which is
    the file created by every ESP-IDF installation.
    """
    p = Path(path_str).expanduser().resolve()   # expand ~ and make absolute
    if p.exists() and (p / "tools" / "cmake" / "project.cmake").exists():
        return p
    return None   # path doesn't look like an ESP-IDF installation


# ── show (default callback) ──────────────────────────────────────────────────

# invoke_without_command=True → run `show` when user types just `config` with no sub-command
@config_app.callback(invoke_without_command=True)
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    if ctx.invoked_subcommand is not None:
        return   # a sub-command was given — let it handle output

    settings = load_settings()
    idf = settings.get("idf", {})
    ai  = settings.get("ai", {})

    # idf_config is the live auto-detected state (used as fallback when no path is saved)
    from analogdata_esp.core.config import idf_config

    # ── ESP-IDF panel ────────────────────────────────────────────────────
    idf_table = Table(show_header=False, box=None, padding=(0, 2))
    idf_table.add_column("Key",   style="bold cyan", no_wrap=True)
    idf_table.add_column("Value", style="white")

    saved_path  = idf.get("path", "")
    saved_tools = idf.get("tools_path", "")

    # Prefer the explicitly-saved path; fall back to whatever was auto-detected
    display_path    = saved_path  or (str(idf_config.idf_path)   if idf_config.idf_path   else "")
    display_tools   = saved_tools or (str(idf_config.tools_path) if idf_config.tools_path else "")
    display_version = idf_config.version or "unknown"
    path_label      = display_path  if display_path  else "[dim](not found)[/dim]"
    tools_label     = display_tools if display_tools else "[dim](not found)[/dim]"
    # Tag the path as "(saved)" if the user explicitly configured it, else "(auto-detected)"
    source_tag = " [dim](saved)[/dim]" if saved_path else " [dim](auto-detected)[/dim]"

    idf_table.add_row("IDF Path",   path_label + (source_tag if display_path else ""))
    idf_table.add_row("Tools Path", tools_label)
    idf_table.add_row("Version",    display_version)

    console.print(Panel(idf_table, title="[bold]ESP-IDF[/bold]", border_style="green"))

    # ── AI provider panel ────────────────────────────────────────────────
    ai_table = Table(show_header=False, box=None, padding=(0, 2))
    ai_table.add_column("Key",   style="bold cyan", no_wrap=True)
    ai_table.add_column("Value", style="white")

    provider = ai.get("provider", "ollama")
    model    = ai.get("model", "")
    api_key  = ai.get("api_key", "")
    base_url = ai.get("base_url", "")

    ai_table.add_row("Provider", provider)
    ai_table.add_row("Model",    model if model else "[dim](default)[/dim]")
    ai_table.add_row("API Key",  _mask_key(api_key))
    # Only show Base URL row for Ollama (cloud providers don't need it)
    if provider == "ollama":
        ai_table.add_row("Base URL", base_url if base_url else "http://localhost:11434")

    console.print(Panel(ai_table, title="[bold]AI Provider[/bold]", border_style="blue"))

    # Show where the config file lives so the user can edit it directly if needed
    console.print(f"\n[dim]Config file: {CONFIG_FILE}[/dim]")


# ── idf sub-command ───────────────────────────────────────────────────────────

@config_app.command()
def idf() -> None:
    """Configure ESP-IDF installation path."""
    console.print("\n[bold]Detecting ESP-IDF installations...[/bold]\n")

    # Scan all known install locations and return matching installations
    found = detect_all_idf()

    if found:
        console.print(f"Found [bold green]{len(found)}[/bold green] ESP-IDF installation(s):\n")
        # List each found installation with a number for selection
        for i, cfg in enumerate(found, start=1):
            version_str = cfg.version or "unknown"
            console.print(f"  [bold cyan]{i}.[/bold cyan] {cfg.idf_path}  [dim](v{version_str})[/dim]")
        # Always add a "manual entry" option at the end
        console.print(f"  [bold cyan]{len(found) + 1}.[/bold cyan] Enter path manually\n")

        while True:
            choice_str = Prompt.ask(
                f"Select [1-{len(found) + 1}]",
                default="1",
            )
            try:
                choice = int(choice_str)
            except ValueError:
                console.print("[red]Please enter a number.[/red]")
                continue

            if 1 <= choice <= len(found):
                # User picked one of the detected installations
                selected_cfg = found[choice - 1]
                chosen_path = str(selected_cfg.idf_path)
                break
            elif choice == len(found) + 1:
                # User wants to type a path manually
                chosen_path = None
                break
            else:
                console.print(f"[red]Enter a number between 1 and {len(found) + 1}.[/red]")
    else:
        # Nothing found automatically — fall straight through to manual entry
        console.print("[yellow]No ESP-IDF installations found automatically.[/yellow]\n")
        chosen_path = None

    # Manual path entry loop — keep asking until a valid path is provided
    while chosen_path is None:
        raw = Prompt.ask("Enter ESP-IDF path (e.g. ~/esp/esp-idf)")
        validated = _validate_idf_path(raw)
        if validated:
            chosen_path = str(validated)
        else:
            console.print(
                f"[red]Invalid ESP-IDF path: {raw!r}[/red]\n"
                "[dim]Expected a directory containing tools/cmake/project.cmake[/dim]\n"
            )

    # Final validation (in case the list choice was somehow invalid)
    final = _validate_idf_path(chosen_path)
    if not final:
        console.print(f"[red]Path validation failed for: {chosen_path}[/red]")
        raise typer.Exit(1)

    # Persist the path to the config file
    settings = load_settings()
    settings["idf"]["path"] = str(final)
    save_settings(settings)

    console.print(
        Panel(
            f"[bold green]Saved![/bold green]\n\nESP-IDF path: [cyan]{final}[/cyan]",
            title="ESP-IDF Configured",
            border_style="green",
        )
    )


# ── ai sub-command ────────────────────────────────────────────────────────────

# Menu entries: (internal name, human-readable label)
_PROVIDER_MENU = [
    ("ollama",    "Ollama (local, no API key needed)"),
    ("openai",    "OpenAI (GPT-4o, GPT-4 Turbo, etc.)"),
    ("anthropic", "Anthropic (Claude)"),
    ("gemini",    "Google Gemini"),
]

# The recommended default model for each provider
_DEFAULT_MODELS = {
    "ollama":    "gemma3:4b",
    "openai":    "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini":    "gemini-2.0-flash",
}


@config_app.command("ai")
def configure_ai() -> None:
    """Configure the AI provider (Ollama, OpenAI, Anthropic, Gemini)."""
    # Load current settings so we can pre-fill prompts with existing values
    current_provider = get_ai_setting("provider") or "ollama"
    current_model    = get_ai_setting("model") or ""
    current_key      = get_ai_setting("api_key") or ""
    current_url      = get_ai_setting("base_url") or ""

    console.print("\n[bold]Select AI provider:[/bold]\n")
    for i, (pname, pdesc) in enumerate(_PROVIDER_MENU, start=1):
        # Mark the currently-active provider with a green label
        marker = " [bold green]<current>[/bold green]" if pname == current_provider else ""
        console.print(f"  [bold cyan]{i}.[/bold cyan] {pdesc}{marker}")
    console.print()

    # Input loop until a valid number is entered
    while True:
        choice_str = Prompt.ask("Select provider [1-4]", default="1")
        try:
            choice = int(choice_str)
            if 1 <= choice <= len(_PROVIDER_MENU):
                break
        except ValueError:
            pass
        console.print(f"[red]Enter a number between 1 and {len(_PROVIDER_MENU)}.[/red]")

    provider_name, _ = _PROVIDER_MENU[choice - 1]
    default_model    = _DEFAULT_MODELS[provider_name]

    # Pre-fill model with the current value if same provider; otherwise use default
    model_default = current_model if (current_model and current_provider == provider_name) else default_model
    model = Prompt.ask("Model name", default=model_default)
    if not model.strip():
        model = default_model   # use default if user presses Enter on empty

    # API key — only needed for cloud providers (not Ollama)
    new_key = current_key
    if provider_name != "ollama":
        masked = _mask_key(current_key) if current_key else "(not set)"
        console.print(f"\nCurrent API key: {masked}")
        # password=True hides the typed characters (like sudo password)
        raw_key = Prompt.ask(
            "API key (Enter to keep current)",
            default="",
            password=True,
        )
        if raw_key.strip():
            new_key = raw_key.strip()

    # Base URL — only relevant for Ollama (allows non-default server address)
    new_url = current_url
    if provider_name == "ollama":
        ollama_default = current_url if current_url else "http://localhost:11434"
        new_url = Prompt.ask("Ollama base URL", default=ollama_default)
        if not new_url.strip():
            new_url = "http://localhost:11434"

    # Quick connectivity check before saving
    console.print("\n[dim]Testing connection...[/dim]")
    available = _test_provider(provider_name, model, new_key, new_url)

    # Save all settings regardless of test result (user might configure offline)
    settings = load_settings()
    settings["ai"]["provider"] = provider_name
    settings["ai"]["model"]    = model
    settings["ai"]["api_key"]  = new_key
    settings["ai"]["base_url"] = new_url if provider_name == "ollama" else ""
    save_settings(settings)

    status = (
        "[bold green]Connection test passed.[/bold green]"
        if available
        else "[bold yellow]Connection test failed — settings saved anyway.[/bold yellow]"
    )
    console.print(
        Panel(
            f"[bold green]Saved![/bold green]\n\n"
            f"Provider: [cyan]{provider_name}[/cyan]\n"
            f"Model:    [cyan]{model}[/cyan]\n\n"
            f"{status}",
            title="AI Provider Configured",
            border_style="blue",
        )
    )


def _test_provider(provider: str, model: str, api_key: str, base_url: str) -> bool:
    """Synchronously test whether the configured provider is reachable.

    Creates the right provider object and calls its async is_available() check.
    Returns True if the provider responds, False on any error.
    """
    try:
        # Import provider classes lazily to avoid loading all AI SDKs on startup
        if provider == "ollama":
            from analogdata_esp.agent.providers.ollama import OllamaProvider
            p = OllamaProvider(base_url=base_url or "http://localhost:11434", model=model or "gemma3:4b")
        elif provider == "openai":
            from analogdata_esp.agent.providers.openai_provider import OpenAIProvider
            p = OpenAIProvider(api_key=api_key, model=model or "gpt-4o")
        elif provider == "anthropic":
            from analogdata_esp.agent.providers.anthropic_provider import AnthropicProvider
            p = AnthropicProvider(api_key=api_key, model=model or "claude-3-5-sonnet-20241022")
        elif provider == "gemini":
            from analogdata_esp.agent.providers.gemini import GeminiProvider
            p = GeminiProvider(api_key=api_key, model=model or "gemini-2.0-flash")
        else:
            return False

        # asyncio.run bridges from synchronous code into the async is_available() call
        return asyncio.run(p.is_available())
    except Exception:
        return False


# ── vscode sub-command ────────────────────────────────────────────────────────

@config_app.command()
def vscode(
    dir: Optional[Path] = typer.Option(
        None, "--dir", "-d",
        help="Project directory. Defaults to current directory (walks up for CMakeLists.txt).",
    ),
) -> None:
    """Generate / fix .vscode/settings.json for the ESP-IDF extension."""
    # write_vscode_settings lives in template.py and builds the settings dict
    # from the auto-detected IDF config, then writes it to disk.
    from analogdata_esp.core.template import write_vscode_settings

    # Walk up from the given (or current) directory to find the project root
    # (the directory that contains CMakeLists.txt)
    here = (dir or Path.cwd()).resolve()
    project_dir = here
    for candidate in [here, *here.parents]:
        if (candidate / "CMakeLists.txt").exists():
            project_dir = candidate
            break

    console.print(f"\n[dim]Writing VS Code settings for:[/dim] [cyan]{project_dir}[/cyan]")
    write_vscode_settings(project_dir)

    from analogdata_esp.core.config import idf_config
    # Show the tools root (parent of the tools/ dir, e.g. ~/.espressif)
    idf_tools_display = str(idf_config.tools_path.parent) if idf_config.tools_path else "(not found)"
    console.print(
        Panel(
            f"[bold green]✅  .vscode/settings.json updated![/bold green]\n\n"
            f"  [bold]ESP-IDF:[/bold]  [cyan]{idf_config.idf_path}[/cyan]\n"
            f"  [bold]Tools:  [/bold]  [cyan]{idf_tools_display}[/cyan]\n\n"
            "[dim]Reload VS Code window for changes to take effect:[/dim]\n"
            "  [cyan]Cmd+Shift+P[/cyan] → [bold]Developer: Reload Window[/bold]",
            title="VS Code Configured",
            border_style="green",
        )
    )


# ── reset sub-command ─────────────────────────────────────────────────────────

@config_app.command()
def reset() -> None:
    """Reset all configuration (delete config file)."""
    if not CONFIG_FILE.exists():
        console.print("[yellow]No config file found — nothing to reset.[/yellow]")
        raise typer.Exit(0)

    # Ask for confirmation before deleting — this is irreversible
    confirmed = Confirm.ask(
        f"[bold red]Delete config file at {CONFIG_FILE}?[/bold red]",
        default=False,   # default to No for safety
    )
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)

    CONFIG_FILE.unlink()   # delete the file
    console.print(
        Panel(
            f"[bold green]Config file deleted.[/bold green]\n\n"
            f"[dim]{CONFIG_FILE}[/dim]",
            title="Reset Complete",
            border_style="green",
        )
    )
