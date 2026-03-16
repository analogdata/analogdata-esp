"""
Agent mode tool registry.

Each Tool has a name, description, JSON-schema parameters, and an execute()
function that runs entirely in-process (no subprocess back to the CLI).

How it works end-to-end:
  1. build_agent_mode_prompt() (base.py) injects tool_schema_block() into the system prompt
  2. The LLM response contains a ```json {"tool": "name", "args": {...}} ``` block
  3. parse_tool_call() extracts that block from the response text
  4. The CLI shows the user an Allow / Dismiss / Edit panel
  5. If allowed, tool.execute(args, cwd) is called and the result printed
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Tool descriptor — one instance per registered tool
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Tool:
    name: str            # must match the "tool" key the LLM produces
    description: str     # shown to the LLM in the system prompt
    parameters: dict     # {param_name: "type — description"} shown in prompt + edit UI
    execute: Callable    # fn(args: dict, cwd: Path) -> str  — returns a status message


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────

def _exec_new_project(args: dict, cwd: Path) -> str:
    """Create a new ESP-IDF project by calling scaffold_project()."""
    from analogdata_esp.core.template import scaffold_project
    from analogdata_esp.core.config import idf_config

    # Normalise name: hyphens and spaces become underscores (valid C identifier)
    name   = args.get("name", "").strip().replace("-", "_").replace(" ", "_")
    target = args.get("target", "esp32").strip()
    # Use the provided path or the current working directory as the parent
    path   = Path(args["path"]).expanduser() if args.get("path") else cwd

    if not name:
        return "❌  Missing argument: name"

    from analogdata_esp.core.template import SUPPORTED_TARGETS
    if target not in SUPPORTED_TARGETS:
        return f"❌  Unknown target '{target}'. Supported: {', '.join(SUPPORTED_TARGETS)}"

    # scaffold_project copies the template, renders Jinja vars, and runs git init
    project_dir = scaffold_project(name=name, target=target, output_dir=path)
    return f"✅  Project created: {project_dir}"


def _exec_run_doctor(args: dict, cwd: Path) -> str:
    """Run a quick environment health check and return a summary string."""
    import shutil
    from analogdata_esp.core.config import idf_config
    from analogdata_esp.core.settings import get_ai_setting

    lines = []
    # Check IDF path
    lines.append(f"ESP-IDF : {'✅ ' + str(idf_config.idf_path) if idf_config.is_valid else '❌  not found'}")
    lines.append(f"Version : {idf_config.version or 'unknown'}")
    # Check build tools on PATH
    lines.append(f"cmake   : {'✅ found' if shutil.which('cmake') else '❌  not found'}")
    lines.append(f"ninja   : {'✅ found' if shutil.which('ninja') else '❌  not found'}")
    lines.append(f"git     : {'✅ found' if shutil.which('git') else '❌  not found'}")
    provider = get_ai_setting("provider") or "ollama"
    lines.append(f"AI      : {provider}")
    return "\n".join(lines)


def _exec_show_config(args: dict, cwd: Path) -> str:
    """Return a formatted string of the current config (IDF path, AI provider)."""
    from analogdata_esp.core.settings import load_settings
    from analogdata_esp.core.config import idf_config

    s   = load_settings()
    idf = s.get("idf", {})
    ai  = s.get("ai", {})
    # Prefer the explicitly-saved path over the auto-detected one
    path = idf.get("path") or str(idf_config.idf_path or "(not found)")
    lines = [
        f"IDF Path : {path}",
        f"Version  : {idf_config.version or 'unknown'}",
        f"Provider : {ai.get('provider', 'ollama')}",
        f"Model    : {ai.get('model') or '(default)'}",
    ]
    return "\n".join(lines)


def _exec_build_project(args: dict, cwd: Path) -> str:
    """Run idf.py build in the project directory and return a concise result."""
    from analogdata_esp.core.idf_runner import run_idf_streaming

    project_dir = Path(args["path"]).expanduser() if args.get("path") else cwd
    idf_args = ["build"]

    lines = []
    ok = True
    # run_idf_streaming yields output lines as they appear (streaming build output)
    for line in run_idf_streaming(idf_args, cwd=project_dir):
        lines.append(line)
        # idf_runner appends "[exit code N]" on non-zero exit
        if line.startswith("[exit code"):
            ok = False

    if ok:
        # Try to surface the binary size line for feedback
        size_line = next((l for l in reversed(lines) if "Project build complete" in l or ".bin" in l), "")
        return f"✅  Build successful.\n{size_line}".strip()
    else:
        # Return the last 10 lines — they almost always contain the compiler error
        tail = "\n".join(lines[-10:])
        return f"❌  Build failed.\n{tail}"


def _exec_flash_project(args: dict, cwd: Path) -> str:
    """Run idf.py flash in the project directory using the auto-detected serial port."""
    from analogdata_esp.core.idf_runner import run_idf_interactive, pick_port

    project_dir = Path(args["path"]).expanduser() if args.get("path") else cwd
    # pick_port returns the explicit override if given, else the first detected port
    port = pick_port(args.get("port"))
    if not port:
        return "❌  No serial port found. Connect your ESP32 and pass port argument."

    idf_args = ["-p", port, "flash"]
    rc = run_idf_interactive(idf_args, cwd=project_dir)   # returns exit code
    if rc == 0:
        return f"✅  Flashed successfully via {port}."
    return f"❌  Flash failed (exit {rc})."


def _exec_monitor_project(args: dict, cwd: Path) -> str:
    """Open the serial monitor — takes over the terminal until the user presses Ctrl+]."""
    from analogdata_esp.core.idf_runner import run_idf_interactive, pick_port

    project_dir = Path(args["path"]).expanduser() if args.get("path") else cwd
    port = pick_port(args.get("port"))
    if not port:
        return "❌  No serial port found. Connect your ESP32 and pass port argument."

    idf_args = ["-p", port, "monitor"]
    run_idf_interactive(idf_args, cwd=project_dir)   # blocks until monitor exits
    return "Monitor closed."


def _exec_set_config_ai(args: dict, cwd: Path) -> str:
    """Update the AI provider (and optionally model/API key) in the config file."""
    from analogdata_esp.core.settings import set_ai_setting

    provider = args.get("provider", "").strip().lower()
    model    = args.get("model", "").strip()
    api_key  = args.get("api_key", "").strip()

    valid = {"ollama", "openai", "anthropic", "gemini"}
    if provider not in valid:
        return f"❌  Unknown provider '{provider}'. Valid: {', '.join(sorted(valid))}"

    set_ai_setting("provider", provider)
    if model:
        set_ai_setting("model", model)
    if api_key:
        set_ai_setting("api_key", api_key)

    return f"✅  AI provider set to {provider}" + (f" / model: {model}" if model else "")


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry — the LLM is told about every tool in this list
# ─────────────────────────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="new_project",
        description="Scaffold a new ESP-IDF project with CMakeLists.txt, main.c, VSCode config, .clangd and .gitignore.",
        parameters={
            "name":   "string — project name (snake_case)",
            "target": "string — chip target: esp32 | esp32s2 | esp32s3 | esp32c2 | esp32c3 | esp32c6 | esp32h2 | esp32p4",
            "path":   "(optional) string — parent directory, defaults to current directory",
        },
        execute=_exec_new_project,
    ),
    Tool(
        name="run_doctor",
        description="Check ESP-IDF installation, toolchain, and AI provider status.",
        parameters={},
        execute=_exec_run_doctor,
    ),
    Tool(
        name="show_config",
        description="Show current ESP-IDF path and AI provider configuration.",
        parameters={},
        execute=_exec_show_config,
    ),
    Tool(
        name="set_config_ai",
        description="Change the AI provider and optionally the model and API key.",
        parameters={
            "provider": "string — ollama | openai | anthropic | gemini",
            "model":    "(optional) string — model name",
            "api_key":  "(optional) string — API key for cloud providers",
        },
        execute=_exec_set_config_ai,
    ),
    Tool(
        name="build_project",
        description="Build an ESP-IDF project using idf.py build. Compiles firmware and reports success or errors.",
        parameters={
            "path": "(optional) string — project directory, defaults to current directory",
        },
        execute=_exec_build_project,
    ),
    Tool(
        name="flash_project",
        description="Flash compiled firmware to a connected ESP32 using idf.py flash.",
        parameters={
            "port": "(optional) string — serial port e.g. /dev/tty.usbserial-0001, auto-detected if omitted",
            "path": "(optional) string — project directory, defaults to current directory",
        },
        execute=_exec_flash_project,
    ),
    Tool(
        name="monitor_project",
        description="Open the serial monitor to see ESP32 output (idf.py monitor). Press Ctrl+] to exit.",
        parameters={
            "port": "(optional) string — serial port, auto-detected if omitted",
            "path": "(optional) string — project directory, defaults to current directory",
        },
        execute=_exec_monitor_project,
    ),
]

# Quick lookup dict: tool name → Tool object used by parse_tool_call and the CLI
TOOL_MAP: dict[str, Tool] = {t.name: t for t in TOOLS}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers used by the system prompt builder and response parser
# ─────────────────────────────────────────────────────────────────────────────

def tool_schema_block() -> str:
    """Return the tools section injected into the agent mode system prompt.

    The LLM reads this so it knows exactly what tools exist and what JSON to output.
    """
    lines = ["Available tools (output ONE JSON block per response, only when an action is needed):"]
    for t in TOOLS:
        # Serialize the parameter schema as indented JSON for readability in the prompt
        params = json.dumps({k: v for k, v in t.parameters.items()}, indent=2) if t.parameters else "{}"
        lines.append(f"\n  {t.name}: {t.description}")
        lines.append(f"  args schema: {params}")
    return "\n".join(lines)


def parse_tool_call(response_text: str) -> Optional[tuple[Tool, dict]]:
    """Extract the first ```json ... ``` block from the response and parse it as a tool call.

    Expected format inside the fenced block:
        {"tool": "<name>", "args": {...}}

    Returns (Tool, args_dict) if a valid tool name is found, or None otherwise.
    """
    import re
    # Match ```json ... ``` — re.DOTALL makes . match newlines so multi-line JSON works
    pattern = re.compile(r'```json\s*(\{.*?\})\s*```', re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(response_text):
        try:
            payload   = json.loads(match.group(1))      # parse the JSON block
            tool_name = payload.get("tool", "").strip()  # "new_project", "build_project", etc.
            args      = payload.get("args", {})          # the argument dict
            if tool_name in TOOL_MAP:
                return TOOL_MAP[tool_name], args          # return the Tool object and its args
        except (json.JSONDecodeError, KeyError):
            continue   # malformed JSON — skip to next match
    return None   # no valid tool call found in this response
