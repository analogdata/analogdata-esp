"""
analogdata-esp new — scaffold a new ESP-IDF project.

Creates a fully-wired project directory with:
  - CMakeLists.txt (project + main component)
  - main/main.c (starter code)
  - .vscode/settings.json (ESP-IDF extension)
  - .clangd (C language server config)
  - .gitignore
  - optional git init + initial commit
"""

import typer
from pathlib import Path
from typing import Optional

# Rich provides the spinner progress display and styled output
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# scaffold_project does the actual file creation; SUPPORTED_TARGETS is the
# list of valid ESP chip identifiers.
from analogdata_esp.core.template import scaffold_project, SUPPORTED_TARGETS

# new_app is used if `new` were ever a sub-app with its own sub-commands.
# Currently it's registered directly on the root app in main.py.
new_app = typer.Typer(help="Scaffold a new ESP-IDF project.")
console = Console()


def new(
    # Positional argument — the project folder name.  Optional so we can prompt.
    name: Optional[str] = typer.Argument(None, help="Project name (snake_case recommended)"),
    # Target chip — defaults to esp32, can be overridden with --target esp32s3
    target: str = typer.Option(
        "esp32",
        "--target", "-t",
        help=f"ESP32 target chip. Options: {', '.join(SUPPORTED_TARGETS)}",
    ),
    # Where to create the project folder.  Defaults to the current directory.
    path: Optional[Path] = typer.Option(
        None,
        "--path", "-p",
        help="Parent directory for the project. Defaults to current directory.",
    ),
    # Skip `git init` if the user doesn't want version control
    no_git: bool = typer.Option(
        False,
        "--no-git",
        help="Skip git init.",
    ),
) -> None:
    """
    Scaffold a new ESP-IDF project with Windsurf/VSCode config,
    .clangd, CMakeLists.txt, and a clean main.c entry point.

    Examples:

        analogdata-esp new blink

        analogdata-esp new sensor_node --target esp32s3

        analogdata-esp new ble_beacon --target esp32c3 --path ~/esp
    """
    # If name wasn't given on the command line, ask for it interactively
    if not name:
        name = typer.prompt("📁  Project name")

    # Normalise name: replace spaces and hyphens with underscores (valid C identifier)
    name = name.strip().replace("-", "_").replace(" ", "_")

    # Reject unknown chip names early with a helpful list
    if target not in SUPPORTED_TARGETS:
        console.print(f"[red]❌ Unknown target: {target}[/red]")
        console.print(f"[dim]Supported: {', '.join(SUPPORTED_TARGETS)}[/dim]")
        raise typer.Exit(1)

    # Use the provided path or fall back to wherever the user currently is
    output_dir = path or Path.cwd()

    # Print a summary before doing any work so the user can see what's about to happen
    console.print()
    console.print(f"[bold cyan]⚡ Creating ESP-IDF project[/bold cyan]")
    console.print(f"   Name   : [green]{name}[/green]")
    console.print(f"   Target : [yellow]{target}[/yellow]")
    console.print(f"   Path   : [dim]{output_dir / name}[/dim]")
    console.print()

    # Show a spinner while the scaffold runs (it calls idf.py set-target which can be slow)
    with Progress(
        SpinnerColumn(),                                       # animated spinner icon
        TextColumn("[progress.description]{task.description}"),  # status text
        console=console,
        transient=True,    # erase the spinner line once done
    ) as progress:
        # Add an indeterminate task (total=None = spinner rather than progress bar)
        task = progress.add_task("Scaffolding project...", total=None)

        try:
            # scaffold_project copies the template, renders Jinja vars, runs git init
            # and optionally runs idf.py set-target + reconfigure.
            project_dir = scaffold_project(
                name=name,
                target=target,
                output_dir=output_dir,
                git_init=not no_git,   # pass True unless user said --no-git
            )
            progress.update(task, description="Done!")
        except FileExistsError:
            # The project directory already exists — don't overwrite
            console.print(f"[red]❌  Project '{name}' already exists at {output_dir / name}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]❌  Failed: {e}[/red]")
            raise typer.Exit(1)

    # Print a success panel with the next steps the user should run
    console.print(
        Panel.fit(
            f"[bold green]✅ Project created:[/bold green] {project_dir}\n\n"
            f"  [dim]cd[/dim] [cyan]{project_dir}[/cyan]\n\n"
            f"  [bold]Build:[/bold]   [cyan]idf.py build[/cyan]\n"
            f"  [bold]Flash:[/bold]   [cyan]idf.py -p /dev/tty.usbserial-* flash[/cyan]\n"
            f"  [bold]Monitor:[/bold] [cyan]idf.py -p /dev/tty.usbserial-* monitor[/cyan]\n"
            f"  [bold]Agent:[/bold]   [cyan]analogdata-esp agent \"your question\"[/cyan]",
            title="[bold]⚡ analogdata-esp[/bold]",
            border_style="green",
        )
    )
