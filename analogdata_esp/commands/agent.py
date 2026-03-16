"""
analogdata-esp agent — ESP-IDF AI assistant.

Two modes:
  Normal mode  — pure Q&A, no side effects, no execution prompts.
  Agent mode   — model can call tools (new_project, run_doctor, build, flash …).
                 Each proposed action shows Allow / Dismiss / Edit before running.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown   # renders Markdown in the terminal (headers, code blocks, etc.)
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule            # horizontal line divider
from rich.table import Table

# ask_agent is the async function that streams tokens from whichever provider is configured
from analogdata_esp.agent.router import ask_agent
# collect_context reads CMakeLists.txt, sdkconfig and build logs for the current project
from analogdata_esp.agent.context import collect_context
# ESP_IDF_SYSTEM_PROMPT = the big system prompt with all idf.py commands
# build_agent_mode_prompt = same but with the tool schema appended
from analogdata_esp.agent.providers.base import ESP_IDF_SYSTEM_PROMPT, build_agent_mode_prompt
# parse_tool_call extracts a JSON tool call from the model response
# TOOL_MAP maps tool names → Tool objects
from analogdata_esp.agent.tools import parse_tool_call, TOOL_MAP

# Typer sub-app — registered as `analogdata-esp agent` in main.py
agent_app = typer.Typer(help="AI agent for ESP-IDF questions.")
console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

# invoke_without_command=True: run this function even when no sub-command is given
@agent_app.callback(invoke_without_command=True)
def agent(
    ctx: typer.Context,
    # Optional positional argument — the question to ask in one-shot mode
    question: Optional[str] = typer.Argument(
        None,
        help="Question to ask. Leave empty for chat mode.",
    ),
    # --chat / -c flag forces interactive chat mode even with no question
    chat: bool = typer.Option(False, "--chat", "-c", help="Start interactive chat."),
    # --no-context skips reading build errors from the project directory
    no_context: bool = typer.Option(False, "--no-context", help="Skip auto-reading build errors."),
    # --dir overrides the project directory for context collection
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d",
                                                help="Project dir for context. Defaults to cwd."),
) -> None:
    """
    Ask the ESP-IDF AI agent a question, or start an interactive chat.

    Normal mode answers questions. Inside chat, type /agent to enable
    agentic mode where the AI can create projects, run checks, and more.

    Examples:

        analogdata-esp agent "why is my FreeRTOS task crashing"

        analogdata-esp agent --chat
    """
    # If this was reached via a sub-command (unlikely here), let the sub-command handle it
    if ctx.invoked_subcommand is not None:
        return

    # If --chat was passed OR no question provided → start interactive loop
    if chat or question is None:
        _run_chat(no_context=no_context, project_dir=project_dir)
    else:
        # One-shot mode: ask a single question, print the answer, exit
        asyncio.run(_ask_once(
            question,
            system=ESP_IDF_SYSTEM_PROMPT,   # standard Q&A system prompt (no tools)
            no_context=no_context,
            project_dir=project_dir,
            agent_mode=False,               # no tool execution in one-shot mode
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Chat loop
# ─────────────────────────────────────────────────────────────────────────────

def _run_chat(no_context: bool, project_dir: Optional[Path]) -> None:
    """Run the interactive multi-turn chat loop until the user types /exit."""
    agent_mode = False   # tracks whether tool execution is enabled this session

    console.print()
    # Welcome panel
    console.print(Panel.fit(
        "[bold cyan]analogdata-esp AI Agent[/bold cyan]\n"
        "[dim]ESP-IDF assistant · type [bold]/agent[/bold] to enable action mode[/dim]\n\n"
        "[dim]Slash commands: /agent  /normal  /exit  /clear  /context  /errors[/dim]",
        border_style="cyan",
    ))
    console.print()

    while True:
        # Show [AGENT] tag in the prompt when tool execution is enabled
        mode_tag = " [bold yellow][AGENT][/bold yellow]" if agent_mode else ""
        try:
            # Prompt.ask blocks until the user types something and presses Enter
            question = Prompt.ask(f"[bold cyan]you{mode_tag}[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C or Ctrl+D — exit gracefully
            console.print("\n[dim]Bye![/dim]")
            break

        question = question.strip()
        if not question:
            continue   # ignore empty input

        # ── Handle slash commands (start with /) ──────────────────────────
        if question == "/exit":
            console.print("[dim]Bye![/dim]")
            break

        elif question == "/clear":
            console.clear()     # wipe the terminal screen
            continue

        elif question == "/agent":
            # Enable tool-use mode — the system prompt now includes the tool schema
            agent_mode = True
            console.print(
                Panel.fit(
                    "[bold yellow]⚡ Agent mode ON[/bold yellow]\n"
                    "[dim]I can now execute actions on your behalf.\n"
                    "Each action will ask for your permission first.\n"
                    "Type [bold]/normal[/bold] to return to Q&A mode.[/dim]",
                    border_style="yellow",
                )
            )
            _print_tool_menu()   # show what tools are available
            console.print()
            continue

        elif question == "/normal":
            # Disable tool-use mode
            agent_mode = False
            console.print("[dim]Switched to normal Q&A mode.[/dim]\n")
            continue

        elif question == "/context":
            # Show the auto-detected project metadata (name, chip, IDF version)
            ctx = collect_context(project_dir)
            console.print(Panel(ctx.as_text() or "[dim]No context found[/dim]",
                                title="Project Context"))
            continue

        elif question == "/errors":
            # Show the last build error lines from build/log/idf_py_stderr_output
            ctx = collect_context(project_dir)
            console.print(Panel(
                ctx.build_error or "[dim]No build errors found[/dim]",
                title="Latest Build Errors",
            ))
            continue

        elif question == "/tools":
            _print_tool_menu()
            continue

        # ── Regular question — send to the LLM ───────────────────────────
        # In agent mode use the richer system prompt that includes the tool schema
        system = build_agent_mode_prompt() if agent_mode else ESP_IDF_SYSTEM_PROMPT
        asyncio.run(_ask_once(
            question,
            system=system,
            no_context=no_context,
            project_dir=project_dir,
            agent_mode=agent_mode,
        ))
        console.print()    # blank line between turns


# ─────────────────────────────────────────────────────────────────────────────
# Core: ask → stream → render → (optionally) execute tool
# ─────────────────────────────────────────────────────────────────────────────

async def _ask_once(
    question: str,
    system: str,
    no_context: bool,
    project_dir: Optional[Path],
    agent_mode: bool,
) -> None:
    """Send one question to the LLM, stream the response, and optionally run a tool."""
    # Collect project context (CMakeLists.txt, sdkconfig, build errors) unless suppressed
    proj_ctx = None
    build_error = None
    if not no_context:
        proj_ctx = collect_context(project_dir)
        build_error = proj_ctx.build_error
        if build_error:
            # Let the user know we've automatically attached the build log
            console.print(
                f"[dim]📋 Auto-attached build errors ({len(build_error.splitlines())} lines)[/dim]"
            )

    console.print()
    console.print(Rule("[dim]agent[/dim]", style="dim"))   # ─── agent ───

    # Stream the response into a string, showing a spinner while waiting
    response_text = ""
    with console.status("[dim]thinking…[/dim]", spinner="dots"):
        # ask_agent is an async generator — each `chunk` is a text token
        async for chunk in ask_agent(
            question=question,
            build_error=build_error,
            context=proj_ctx.as_text() if proj_ctx else None,
            system_override=system,
        ):
            response_text += chunk

    # Render the response as Markdown (the LLM uses code fences, headers, etc.)
    # In agent mode, strip the raw JSON tool-call block before displaying
    display_text = _strip_json_block(response_text) if agent_mode else response_text
    console.print(Markdown(display_text))
    console.print(Rule(style="dim"))

    # In agent mode, check if the model included a tool call and offer to run it
    if agent_mode:
        _handle_tool_call(response_text, cwd=project_dir or Path.cwd())


def _strip_json_block(text: str) -> str:
    """Remove the ```json ... ``` fenced block from the response text.

    The raw JSON tool call is internal scaffolding — we show it separately
    in the action panel, not inline in the rendered Markdown.
    """
    import re
    # re.DOTALL makes `.` match newlines so multi-line JSON blocks are caught
    return re.sub(r'\n?```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Tool execution with Allow / Dismiss / Edit
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_call(response_text: str, cwd: Path) -> None:
    """Parse a tool call from the response and ask the user to approve it."""
    # parse_tool_call scans for a ```json {"tool": ..., "args": ...} ``` block
    result = parse_tool_call(response_text)
    if result is None:
        return   # no tool call in this response — nothing to do

    tool, args = result
    _show_action_panel(tool, args)   # display what the agent wants to do

    console.print()
    # Give the user three choices:  a = allow, d = dismiss, e = edit args first
    action = Prompt.ask(
        "  [bold green]Allow[/bold green]  [dim]Dismiss[/dim]  [cyan]Edit[/cyan]",
        choices=["a", "d", "e"],
        default="d",          # dismiss by default — safety first
        show_choices=False,   # suppress the "(a/d/e)" hint since labels are in the prompt
    ).lower()

    if action == "d":
        console.print("[dim]Action dismissed.[/dim]")
        return

    if action == "e":
        # Let the user modify individual arguments before running
        args = _edit_args(tool, args)
        if args is None:
            console.print("[dim]Action cancelled.[/dim]")
            return

    # Execute the tool with the (possibly edited) arguments
    console.print()
    try:
        result_msg = tool.execute(args, cwd)   # returns a status string
        console.print(result_msg)
    except Exception as e:
        console.print(f"[red]❌  Action failed: {e}[/red]")


def _show_action_panel(tool, args: dict) -> None:
    """Display a panel showing the tool name and its arguments."""
    # Build a two-column key/value table for the args
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key",   style="bold cyan", no_wrap=True)
    table.add_column("value", style="white")
    table.add_row("tool", tool.name)
    for k, v in args.items():
        table.add_row(k, str(v))
    console.print()
    console.print(Panel(table, title="[bold yellow]⚡ Proposed action[/bold yellow]",
                        border_style="yellow"))


def _edit_args(tool, current_args: dict) -> Optional[dict]:
    """Let the user edit each argument value before the tool runs.

    Returns the updated args dict, or None if the user left everything blank.
    """
    console.print("[dim]Edit arguments (press Enter to keep current value):[/dim]")
    new_args = {}
    # Iterate over the tool's parameter schema to know which args to ask about
    for key, schema_desc in tool.parameters.items():
        key_clean = key.rstrip("?")                      # remove optional marker
        current = current_args.get(key_clean, "")
        # Show the arg name and its type hint (e.g. "string — project name")
        user_input = Prompt.ask(
            f"  [cyan]{key_clean}[/cyan] [dim]({schema_desc.split('—')[0].strip()})[/dim]",
            default=str(current) if current else "",
        )
        if user_input:
            new_args[key_clean] = user_input
        elif current:
            new_args[key_clean] = current   # keep existing value if Enter was pressed
    return new_args if new_args else None


def _print_tool_menu() -> None:
    """Display a table of all registered tools and their parameters."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("tool",   style="bold cyan", no_wrap=True)
    table.add_column("desc",   style="white")
    for t in TOOL_MAP.values():
        # Show param names as a comma-separated list on a dim second line
        params = ", ".join(k.rstrip("?") for k in t.parameters) or "—"
        table.add_row(t.name, f"{t.description}\n[dim]args: {params}[/dim]")
    console.print(Panel(table, title="[bold]Available tools[/bold]", border_style="cyan"))
