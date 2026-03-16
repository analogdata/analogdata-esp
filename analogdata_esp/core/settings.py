"""Persistent configuration stored at ~/.config/analogdata-esp/config.toml.

All user preferences (IDF path, AI provider, API keys) live in a single TOML
file so they survive between terminal sessions.  The functions in this module
are the only place that reads or writes that file.
"""
import os
import tomllib          # stdlib TOML parser (Python 3.11+, read-only)
from pathlib import Path

# Location of the config file — follows XDG convention on Linux/macOS
CONFIG_DIR  = Path.home() / ".config" / "analogdata-esp"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Default values used when the file doesn't exist or a key is missing.
# Structured as nested dicts that mirror the TOML sections [idf] and [ai].
_DEFAULT_SETTINGS = {
    "idf": {
        "path": "",        # filesystem path to the ESP-IDF repo
        "tools_path": "",  # ~/.espressif/tools (auto-detected if blank)
    },
    "ai": {
        "provider": "ollama",  # which LLM backend to use
        "model": "",           # model name (blank = use provider default)
        "api_key": "",         # API key for cloud providers
        "base_url": "",        # custom endpoint for Ollama or OpenAI-compatible APIs
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` into `base` recursively, returning a new dict.

    Nested dicts are merged key-by-key so that a partial config file
    (e.g. only [ai] set) still gets all [idf] defaults.
    """
    result = dict(base)                         # shallow copy of base
    for key, value in override.items():
        # If both base and override have a dict at this key, recurse into it
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value                 # override wins for non-dict values
    return result


def load_settings() -> dict:
    """Load settings from config file, returning defaults for missing keys.

    Returns a fully-populated dict regardless of whether the file exists.
    """
    if not CONFIG_FILE.exists():
        # No file yet — return factory defaults
        return _deep_merge({}, _DEFAULT_SETTINGS)
    try:
        # tomllib.load requires a binary file handle; it only reads, never writes
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        # Merge saved data ON TOP of defaults so missing keys get default values
        return _deep_merge(_DEFAULT_SETTINGS, data)
    except Exception:
        # Corrupt or unreadable file — silently fall back to defaults
        return _deep_merge({}, _DEFAULT_SETTINGS)


def _toml_value(v) -> str:
    """Serialize a single Python value to its TOML literal representation.

    Used by _write_toml to build the file contents as a string.
    """
    if isinstance(v, bool):
        return "true" if v else "false"    # TOML booleans are lowercase
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    if isinstance(v, str):
        # Escape backslashes and double-quotes so the string is valid TOML
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(v, list):
        # TOML inline array: [item1, item2, ...]
        items = ", ".join(_toml_value(i) for i in v)
        return f"[{items}]"
    # Fallback: treat anything else as a quoted string
    return f'"{v}"'


def _write_toml(data: dict) -> str:
    """Manually serialize a two-level dict to TOML text.

    We hand-roll this instead of using a third-party writer to avoid adding
    a dependency just for config saves.  The format is:

        key = "value"       ← top-level scalar (rare)

        [section]
        key = "value"       ← nested dict becomes a section
    """
    lines = []
    # First pass: emit any top-level scalar keys (uncommon in our schema)
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_toml_value(value)}")
    # Second pass: emit each section header and its key-value pairs
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"\n[{key}]")               # e.g. [ai]
            for k, v in value.items():
                lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines) + "\n"


def save_settings(settings: dict) -> None:
    """Write the settings dict back to the config file.

    Creates the config directory if it doesn't exist yet.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)   # mkdir -p equivalent
    content = _write_toml(settings)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(content)


# ── Convenience accessors — used throughout the codebase ─────────────────────

def get_ai_setting(key: str) -> str:
    """Return a single value from the [ai] section (empty string if not set)."""
    settings = load_settings()
    return settings.get("ai", {}).get(key, "")


def set_ai_setting(key: str, value: str) -> None:
    """Update one key in the [ai] section and persist immediately."""
    settings = load_settings()
    if "ai" not in settings:
        settings["ai"] = {}
    settings["ai"][key] = value
    save_settings(settings)


def get_idf_setting(key: str) -> str:
    """Return a single value from the [idf] section (empty string if not set)."""
    settings = load_settings()
    return settings.get("idf", {}).get(key, "")


def set_idf_setting(key: str, value: str) -> None:
    """Update one key in the [idf] section and persist immediately."""
    settings = load_settings()
    if "idf" not in settings:
        settings["idf"] = {}
    settings["idf"][key] = value
    save_settings(settings)
