"""
Unified interactive shell for analogdata-esp.

Just run `analogdata-esp` (no arguments) to enter the shell.

  new blink --target esp32s3   → run CLI commands directly
  doctor                       → health check
  config / config ai / config idf
  /agent                       → enter AI conversation mode
  /help  /clear  /exit
"""

from __future__ import annotations

import asyncio       # runs async AI streaming code from the synchronous shell loop
import os            # os.chdir() for the built-in 'cd' command
import re            # regex for stripping JSON blocks from AI responses
import shlex         # splits 'cmd "arg with spaces"' like a real shell
import subprocess    # runs unknown commands (ls, git, etc.) as system processes
from pathlib import Path        # clean cross-platform path handling
from typing import Optional

import typer
from rich.console import Console          # Rich terminal output (colours, markup)
from rich.markdown import Markdown        # renders Markdown-formatted AI responses
from rich.panel import Panel              # draws bordered boxes around content
from rich.prompt import Confirm, Prompt   # interactive y/n and text prompts
from rich.rule import Rule                # horizontal divider lines
from rich.table import Table              # formatted tables

# Internal modules — the AI router, prompt builder, tool system, and context scanner
from analogdata_esp.agent.router import ask_agent
from analogdata_esp.agent.providers.base import build_agent_mode_prompt
from analogdata_esp.agent.tools import parse_tool_call, TOOL_MAP
from analogdata_esp.agent.context import collect_context, ProjectContext

# Module-level Rich console — all shell output goes through this
console = Console()
# Version string shown in the welcome panel
_VERSION = "v0.1.0"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def open_shell(app: typer.Typer) -> None:
    """Launch the interactive command shell.

    This is the main REPL (Read-Eval-Print Loop):
      1. Show the welcome panel on startup.
      2. Read a line of input from the user.
      3. Dispatch it: slash commands (/agent, /help, /exit) or CLI commands.
      4. Repeat until exit.

    Args:
        app: The root Typer app — used to dispatch CLI commands typed in the shell.
    """
    _print_welcome()   # show the command cheat-sheet on startup

    while True:
        try:
            # Show current directory name in the prompt so user knows where they are
            # e.g.  "analogdata-esp blink ❯"
            cwd_name = Path.cwd().name or str(Path.cwd())
            line = Prompt.ask(
                f"[bold cyan]analogdata-esp[/bold cyan] [dim]{cwd_name}[/dim] [bold]❯[/bold]"
            )
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C or Ctrl+D — clean exit (EOFError happens when stdin is piped)
            console.print("\n[dim]Bye![/dim]")
            break

        line = line.strip()
        if not line:
            continue   # blank input — just show the prompt again

        # ── Slash commands ──────────────────────────────────────────────────
        # Lines starting with "/" are shell meta-commands, not CLI commands
        if line.startswith("/"):
            # Take only the first token in case user types "/agent hello" etc.
            slug = line.lower().split()[0]

            if slug in ("/exit", "/quit"):
                console.print("[dim]Bye![/dim]")
                break

            elif slug == "/agent":
                # Enter the multi-turn AI conversation REPL
                _agent_mode()

            elif slug == "/help":
                _print_help()

            elif slug == "/clear":
                # Wipe the screen and re-draw the welcome panel
                console.clear()
                _print_welcome()

            else:
                # Unrecognised slash command — suggest /help
                console.print(
                    f"[yellow]Unknown command: {slug}[/yellow]  "
                    "(type [bold cyan]/help[/bold cyan] for available commands)"
                )
            continue   # don't fall through to _dispatch for slash commands

        # Allow typing "exit" / "quit" without slash too
        if line.lower() in ("exit", "quit"):
            console.print("[dim]Bye![/dim]")
            break

        # ── Dispatch to Click ───────────────────────────────────────────────
        # Everything else (e.g. "build", "new blink --target esp32s3") is passed
        # to the Typer/Click CLI app which routes it to the right command function
        _dispatch(app, line)


# ─────────────────────────────────────────────────────────────────────────────
# Command dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch(app: typer.Typer, line: str) -> None:
    """Parse a command string and forward it to the Typer/Click app.

    shlex.split handles quoted arguments correctly, e.g.:
      new "my project" --target esp32s3
      → ["new", "my project", "--target", "esp32s3"]

    Args:
        app:  Root Typer app (already registered with all commands).
        line: Raw input string from the user.
    """
    try:
        # Split the string the same way a shell would — respects quotes and backslashes
        parts = shlex.split(line)
    except ValueError as e:
        # Malformed input like unmatched quote: new "blink
        console.print(f"[red]Parse error: {e}[/red]")
        return

    if not parts:
        return

    # Strip binary prefix so typing "analogdata-esp build" still works
    # The user might copy-paste from docs which include the binary name
    if parts[0].lower() in ("analogdata-esp", "ad-esp", "ae"):
        parts = parts[1:]
        if not parts:
            _print_help()   # bare "analogdata-esp" → show help
            return

    try:
        # standalone_mode=False → Click raises UsageError instead of calling sys.exit()
        # This lets us catch errors and show them gracefully instead of quitting the shell
        app(parts, standalone_mode=False)
    except SystemExit:
        # Normal Click exit on --help or explicit Exit(0) — ignore it to keep shell alive
        pass
    except Exception as e:
        msg = str(e)
        # "No such command 'ls'" → fall through to the OS shell (ls, git, etc.)
        if msg and "no such command" in msg.lower():
            _run_system_command(parts)
        elif msg:
            # Real error — show it in red
            console.print(f"[red]{msg}[/red]")


def _run_system_command(parts: list[str]) -> None:
    """
    Pass unknown commands through to the OS shell.

    `cd` is handled specially — it must change the Python process's own cwd
    because subprocess.run() would only change the child process's cwd.
    Everything else is run via subprocess so the user can use `ls`, `pwd`,
    `cat`, `git`, etc. directly inside the shell.

    Args:
        parts: Tokenised command, e.g. ["ls", "-la"] or ["cd", ".."]
    """
    cmd = parts[0]

    # ── cd ───────────────────────────────────────────────────────────────────
    if cmd == "cd":
        # Default to home directory if no argument given (Unix convention: bare "cd")
        target = parts[1] if len(parts) > 1 else str(Path.home())
        try:
            os.chdir(target)   # change the shell process's working directory
            console.print(f"[dim]{Path.cwd()}[/dim]")   # confirm new directory
        except FileNotFoundError:
            console.print(f"[red]cd: {target}: No such file or directory[/red]")
        except PermissionError:
            console.print(f"[red]cd: {target}: Permission denied[/red]")
        return

    # ── pwd ──────────────────────────────────────────────────────────────────
    if cmd == "pwd":
        console.print(str(Path.cwd()))
        return

    # ── everything else ───────────────────────────────────────────────────────
    # Run command with the current cwd so the user sees output in context
    try:
        subprocess.run(parts, cwd=str(Path.cwd()))
    except FileNotFoundError:
        # Binary doesn't exist on PATH at all
        console.print(
            f"[red]Command not found: {cmd}[/red]  "
            "[dim](type [bold cyan]/help[/bold cyan] for available commands)[/dim]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent conversation mode
# ─────────────────────────────────────────────────────────────────────────────

def _agent_mode() -> None:
    """Enter the AI agent conversation loop.

    Runs until the user types /back or /exit.

    The agent loop:
      1. Scans the current directory for project context (project name, target chip, errors).
      2. Shows a banner with what was detected.
      3. Reads questions from the user.
      4. Streams AI responses via ask_agent().
      5. If the AI proposes a tool call (JSON block), asks Allow/Dismiss.
      6. Appends each turn to `history` for multi-turn memory.
    """
    # ── Collect project context from current directory ──────────────────────
    # collect_context() reads CMakeLists.txt, sdkconfig, and build logs
    proj_ctx = collect_context(Path.cwd())
    ctx_text  = proj_ctx.as_text()   # formatted text like "Project: blink\nTarget: esp32s3"
    build_err = proj_ctx.build_error  # last build errors, auto-attached to AI queries

    # ── Banner ───────────────────────────────────────────────────────────────
    console.print()
    banner_lines = ["[bold yellow]⚡ Agent mode[/bold yellow]"]

    if ctx_text:
        # Show each detected context line indented and in cyan
        banner_lines.append("")
        banner_lines.append("[dim]Project context detected:[/dim]")
        for line in ctx_text.splitlines():
            banner_lines.append(f"  [cyan]{line}[/cyan]")
    if build_err:
        # Warn the user that build errors are automatically sent with every query
        banner_lines.append(
            f"  [yellow]⚠  Build errors found[/yellow] [dim]({len(build_err.splitlines())} lines — auto-attached)[/dim]"
        )
    if not ctx_text:
        banner_lines.append("[dim]No ESP-IDF project detected in current directory.[/dim]")

    # Tips shown at the bottom of the banner
    banner_lines += [
        "",
        "[dim]Chat naturally. The AI knows your project context.[/dim]",
        "[dim]It will ask permission before running any action.[/dim]",
        "[dim]Type [bold]/back[/bold] to return to the shell.[/dim]",
    ]
    console.print(Panel.fit("\n".join(banner_lines), border_style="yellow"))
    _print_tool_menu()   # show which agent tools are available
    console.print()

    # Multi-turn conversation history — grows as the conversation progresses
    # Each entry: {"role": "user"|"assistant", "content": "..."}
    history: list[dict] = []

    while True:
        try:
            # Yellow ◉ prompt distinguishes agent mode from the main shell prompt
            question = Prompt.ask(
                "[bold yellow]◉[/bold yellow] [bold]❯[/bold]"
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Back to shell.[/dim]")
            break

        question = question.strip()
        if not question:
            continue

        # Agent-mode slash commands — handled before sending to AI
        slug = question.lower()

        if slug in ("/back", "/exit", "/shell"):
            # Return to main shell
            console.print("[dim]Back to shell.[/dim]")
            break

        if slug == "/clear":
            console.clear()
            continue

        if slug == "/tools":
            # Show the tool menu again (user may have scrolled past it)
            _print_tool_menu()
            continue

        if slug == "/history":
            # Print a condensed view of the conversation so far
            _print_history(history)
            continue

        if slug == "/reset":
            # Forget previous turns — next question starts fresh
            history.clear()
            console.print("[dim]Conversation history cleared.[/dim]")
            continue

        if slug in ("/context", "/ctx"):
            # Show what project context was detected in the current directory
            _print_context(proj_ctx)
            continue

        if slug == "/refresh":
            # Re-scan disk — useful after a build or config change
            proj_ctx = collect_context(Path.cwd())
            ctx_text  = proj_ctx.as_text()
            build_err = proj_ctx.build_error
            console.print("[dim]Project context refreshed.[/dim]")
            if ctx_text:
                for line in ctx_text.splitlines():
                    console.print(f"  [cyan]{line}[/cyan]")
            continue

        # ── Send the question to the AI ─────────────────────────────────────
        # asyncio.run() bridges from this synchronous loop into the async AI streaming code
        response = asyncio.run(
            _stream_response(question, history, ctx_text or None, build_err)
        )

        # Store this turn in history so the AI remembers it next question
        history.append({"role": "user",      "content": question})
        history.append({"role": "assistant", "content": response})

        # If the AI proposed a tool call, show it and ask Allow/Dismiss
        _handle_tool_call(response)


async def _stream_response(
    question: str,
    history: list[dict],
    context: Optional[str] = None,
    build_error: Optional[str] = None,
) -> str:
    """Stream AI response tokens, render as Markdown, and return the full text.

    Steps:
      1. Build the agent-mode system prompt (includes tool schema).
      2. Show a spinner while the first token arrives ("thinking…").
      3. Collect all streamed tokens into response_text.
      4. Strip the raw JSON tool block (shown separately via the action panel).
      5. Render the cleaned text as Markdown for readable formatting.

    Args:
        question:    Current user question.
        history:     Previous conversation turns for multi-turn memory.
        context:     Project metadata string (project name, chip, IDF version).
        build_error: Last build error log, auto-attached to the prompt.

    Returns:
        Full raw response text (including any JSON tool block).
    """
    # Use the extended system prompt that includes the tool schema
    # (so the AI knows it can output JSON tool calls)
    system = build_agent_mode_prompt()

    # One-time notice when build errors are being auto-attached for the first time
    if build_error and not any("[build errors attached]" in m["content"] for m in history[:1]):
        console.print(
            f"[dim]📋 Build errors auto-attached ({len(build_error.splitlines())} lines)[/dim]"
        )

    console.print()
    console.print(Rule("[dim]agent[/dim]", style="dim"))  # visual separator before response

    response_text = ""
    # Show a spinner while waiting for the first token from the AI
    with console.status("[dim]thinking…[/dim]", spinner="dots"):
        # ask_agent() is an async generator that yields text chunks as they stream in
        async for chunk in ask_agent(
            question=question,
            system_override=system,    # agent-mode prompt with tool schema
            history=history,
            context=context,
            build_error=build_error,
        ):
            response_text += chunk   # accumulate all chunks into the full response

    # Remove the JSON code block before rendering — it's shown via the action panel instead
    display = _strip_json_block(response_text)
    # Render the remaining text as Markdown (code fences, bold, etc.)
    console.print(Markdown(display))
    console.print(Rule(style="dim"))   # visual separator after response
    console.print()

    return response_text   # return raw text (with JSON) so caller can parse tool calls


def _strip_json_block(text: str) -> str:
    """Remove ```json {...} ``` blocks from text before Markdown rendering.

    The JSON tool call block is shown separately in the action panel,
    so we strip it here to avoid printing raw JSON to the user.

    re.DOTALL makes `.` match newlines so multi-line JSON blocks are caught.
    """
    return re.sub(r"\n?```json\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Tool execution — Allow / Dismiss  (y / n)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_call(response_text: str) -> None:
    """If the AI response contains a tool call, show it and ask for confirmation.

    The AI sometimes outputs a JSON block at the end of its response:
        ```json
        {"tool": "build_project", "args": {}}
        ```

    This function:
      1. Parses the JSON tool call (if any).
      2. Displays a "Proposed action" panel so the user sees exactly what will run.
      3. Asks y/n — only executes if the user confirms.

    This is the safety gate: the AI never executes anything without explicit user approval.

    Args:
        response_text: Full raw AI response (may contain a JSON tool block).
    """
    # parse_tool_call extracts the JSON and looks up the tool in TOOL_MAP
    result = parse_tool_call(response_text)
    if result is None:
        return   # no tool call in this response — nothing to do

    tool, args = result   # tool is a Tool object, args is the parsed dict

    # ── Build the action summary table ──────────────────────────────────────
    # Show "tool: build_project" then each argument on its own row
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key",   style="bold cyan",  no_wrap=True)
    table.add_column("value", style="white")
    table.add_row("tool", f"[bold]{tool.name}[/bold]")
    for k, v in args.items():
        table.add_row(k, str(v))

    console.print(Panel(
        table,
        title="[bold yellow]⚡ Proposed action[/bold yellow]",
        border_style="yellow",
    ))

    # ── Ask the user before running anything ────────────────────────────────
    # default=False so pressing Enter without typing dismisses the action
    if Confirm.ask(
        "  [bold green]Allow[/bold green] this action?",
        default=False,
    ):
        console.print()
        try:
            # tool.execute() runs the action (e.g. builds the project, creates files)
            msg = tool.execute(args, Path.cwd())
            console.print(msg)   # success message from the tool
        except Exception as e:
            console.print(f"[red]❌  Action failed: {e}[/red]")
    else:
        # User pressed n / Enter — no action taken
        console.print("[dim]Action dismissed.[/dim]")

    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_welcome() -> None:
    """Print the startup welcome panel with a cheat-sheet of available commands.

    Uses a Rich Table.grid (no borders, just columns) for alignment,
    wrapped in a Panel with the version number in the title.
    The footer row shows the slash commands (/agent, /help, /clear, /exit).
    """
    from rich.table import Table as _Table
    console.print()

    # Table.grid — like a table but no borders, just spaced columns
    t = _Table.grid(padding=(0, 3))
    t.add_column(style="bold green",  no_wrap=True)   # command name column
    t.add_column(style="dim white")                    # description column

    t.add_row("new <name> --target <chip>", "Scaffold a new ESP-IDF project")
    t.add_row("build",                      "Compile firmware  (idf.py build)")
    t.add_row("flash  [--port <port>]",     "Flash to ESP32  (idf.py flash)")
    t.add_row("monitor  [--port <port>]",   "Serial console  (idf.py monitor)")
    t.add_row("flash-monitor",              "Flash then open monitor")
    t.add_row("menuconfig",                 "Open sdkconfig editor  (idf.py menuconfig)")
    t.add_row("doctor",                     "Check environment health")
    t.add_row("config",                     "Configure IDF path + AI provider")
    t.add_row("config vscode",              "Fix VS Code / ESP-IDF extension settings")

    # Build the footer Text object with styled segments
    from rich.text import Text
    footer = Text()
    footer.append("/agent", style="bold yellow")
    footer.append("   Enter AI conversation mode   ", style="dim white")
    footer.append("/help", style="bold cyan")
    footer.append("  ", style="")
    footer.append("/clear", style="bold cyan")
    footer.append("  ", style="")
    footer.append("/exit", style="bold cyan")

    console.print(Panel(
        t,
        title=f"[bold]⚡ Analog Data ESP Shell[/bold]  [dim]{_VERSION}[/dim]",
        subtitle=footer,     # shown at the bottom of the panel border
        border_style="cyan",
        padding=(1, 2),      # 1 line top/bottom, 2 chars left/right inside panel
    ))
    console.print()


def _print_help() -> None:
    """Print the full help panel with three sections: Commands, Shell, Agent mode.

    Groups commands into:
      - Commands: CLI commands the user can type directly
      - Shell: /slash commands for shell navigation
      - Agent mode: /slash commands available inside agent mode
    """
    from rich.table import Table as _T
    from rich.text import Text as _Txt

    # ── Commands table ──────────────────────────────────────────────────────
    cmds = _T.grid(padding=(0, 3))
    cmds.add_column(style="bold green", no_wrap=True)
    cmds.add_column(style="white")
    cmds.add_row(
        "new <name> --target <chip>",
        "Scaffold an ESP-IDF project\n"
        "[dim]chips: esp32 esp32s2 esp32s3 esp32c2 esp32c3 esp32c6 esp32h2 esp32p4[/dim]",
    )
    cmds.add_row("", "")   # blank spacer row
    cmds.add_row(
        "build  [--dir <path>]  [-j N]",
        "Compile firmware  [dim](idf.py build — no export.sh needed)[/dim]",
    )
    cmds.add_row(
        "flash  [--port <port>]",
        "Flash firmware to ESP32  [dim](port auto-detected)[/dim]",
    )
    cmds.add_row(
        "monitor  [--port <port>]",
        "Open serial monitor  [dim](Ctrl+] to exit)[/dim]",
    )
    cmds.add_row(
        "flash-monitor  [--port <port>]",
        "Flash then immediately open monitor",
    )
    cmds.add_row(
        "menuconfig  [--dir <path>]",
        "Open interactive sdkconfig editor  [dim](idf.py menuconfig)[/dim]",
    )
    cmds.add_row("", "")   # spacer
    cmds.add_row("doctor",               "Check ESP-IDF, toolchains, cmake, ninja, AI provider")
    cmds.add_row("config",               "Show current settings")
    cmds.add_row("config idf",           "Set ESP-IDF path")
    cmds.add_row("config ai",            "Set AI provider (ollama / openai / anthropic / gemini)")
    cmds.add_row("config vscode",        "Fix .vscode/settings.json for the ESP-IDF extension")
    cmds.add_row('agent "<question>"',   "Ask the AI a one-off question")

    # ── Shell commands table ────────────────────────────────────────────────
    shell_cmds = _T.grid(padding=(0, 3))
    shell_cmds.add_column(style="bold yellow", no_wrap=True)
    shell_cmds.add_column(style="white")
    shell_cmds.add_row("/agent",   "Enter AI conversation mode")
    shell_cmds.add_row("/help",    "Show this help")
    shell_cmds.add_row("/clear",   "Clear the screen")
    shell_cmds.add_row("/exit",    "Exit the shell")

    # ── Agent mode commands table ────────────────────────────────────────────
    agent_cmds = _T.grid(padding=(0, 3))
    agent_cmds.add_column(style="bold cyan", no_wrap=True)
    agent_cmds.add_column(style="white")
    agent_cmds.add_row("/back",    "Return to command shell")
    agent_cmds.add_row("/tools",   "List available agent tools")
    agent_cmds.add_row("/context", "Show detected project context")
    agent_cmds.add_row("/refresh", "Re-scan project context from disk")
    agent_cmds.add_row("/history", "Review conversation so far")
    agent_cmds.add_row("/reset",   "Clear conversation history")

    # Rich Group renders multiple renderables as a vertical stack inside one Panel
    from rich.console import Group
    content = Group(
        "[bold]Commands[/bold]  [dim](type directly — no analogdata-esp prefix needed)[/dim]\n",
        cmds,
        "\n[bold]Shell[/bold]\n",
        shell_cmds,
        "\n[bold]Agent mode[/bold]  "
        "[dim](chat naturally · AI proposes actions · confirm with [/dim]"
        "[green]y[/green][dim]/[/dim][red]n[/red][dim])[/dim]\n",
        agent_cmds,
    )
    console.print(Panel(content, title="[bold]Help[/bold]", border_style="cyan", padding=(1, 2)))


def _print_tool_menu() -> None:
    """Print a summary table of all available agent tools.

    Iterates TOOL_MAP (the registry of agent-callable tools) and shows
    each tool's name, description, and accepted argument names.
    The trailing '?' convention marks optional arguments — strip it for display.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("tool", style="bold cyan",  no_wrap=True)
    table.add_column("desc", style="white")
    for t in TOOL_MAP.values():
        # Strip trailing "?" from optional param names for cleaner display
        params = ", ".join(k.rstrip("?") for k in t.parameters) or "—"
        table.add_row(
            t.name,
            f"{t.description}\n[dim]args: {params}[/dim]",
        )
    console.print(Panel(
        table,
        title="[bold]Available agent tools[/bold]",
        border_style="yellow",
    ))


def _print_history(history: list[dict]) -> None:
    """Print conversation history — role label + first 200 chars of content.

    Shows user messages with yellow ◉ and assistant messages with cyan "agent".
    Truncates long messages to 200 chars to keep the display readable.

    Args:
        history: List of {"role": ..., "content": ...} dicts.
    """
    if not history:
        console.print("[dim]No conversation history yet.[/dim]")
        return
    for msg in history:
        # Different styles for user vs assistant messages
        role = "[bold yellow]◉[/bold yellow]" if msg["role"] == "user" else "[bold cyan]agent[/bold cyan]"
        text = msg["content"]
        # Truncate very long messages so history stays readable
        preview = (text[:200] + "…") if len(text) > 200 else text
        console.print(f"{role}  {preview}\n")


def _print_context(proj_ctx: ProjectContext) -> None:
    """Print the currently loaded project context.

    Shows project name, target chip, IDF version, and build status
    in a neat panel. If nothing was detected, gives a helpful hint
    to navigate into a project directory first.

    Args:
        proj_ctx: ProjectContext populated by collect_context().
    """
    lines = []
    if proj_ctx.project_name:
        lines.append(f"[bold]Project[/bold]     {proj_ctx.project_name}")
    if proj_ctx.idf_target:
        lines.append(f"[bold]Target[/bold]      {proj_ctx.idf_target}")
    if proj_ctx.idf_version:
        lines.append(f"[bold]IDF version[/bold] {proj_ctx.idf_version}")
    if proj_ctx.has_build:
        lines.append("[bold]Built[/bold]       yes (sdkconfig found)")
    if proj_ctx.build_error:
        n = len(proj_ctx.build_error.splitlines())
        lines.append(f"[bold]Build errors[/bold] {n} lines (auto-attached to queries)")

    if lines:
        console.print(Panel(
            "\n".join(lines),
            title="[bold]Project context[/bold]",
            border_style="cyan",
        ))
    else:
        console.print(
            "[dim]No ESP-IDF project detected in current directory.\n"
            "Navigate into a project folder first, then /refresh.[/dim]"
        )
