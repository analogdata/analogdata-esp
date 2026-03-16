# Configuration Overview

`analogdata-esp` stores all persistent configuration in a single TOML file. This page explains where the file lives, what it contains, and how to manage it.

---

## Config File Location

| Platform | Path |
|---|---|
| macOS / Linux | `~/.config/analogdata-esp/config.toml` |
| Windows | `%APPDATA%\analogdata-esp\config.toml` |

The file and its parent directory are created automatically the first time you run a config wizard.

---

## Config File Structure

The config file has two top-level sections:

```toml
[idf]
path = "/home/user/esp/esp-idf"
tools_path = "/home/user/.espressif"

[ai]
provider = "ollama"
model = "gemma3:4b"
# api_key is stored here only if you choose to save it
# api_key = "sk-..."
```

### `[idf]` section

| Key | Description |
|---|---|
| `path` | Absolute path to the root of the ESP-IDF installation |
| `tools_path` | Absolute path to the ESP-IDF tools directory (usually `~/.espressif`) |

### `[ai]` section

| Key | Description |
|---|---|
| `provider` | One of `ollama`, `openai`, `anthropic`, `gemini` |
| `model` | Model name specific to the chosen provider |
| `api_key` | API key (optional — can use environment variables instead) |

---

## Managing Configuration

All configuration is managed through the `analogdata-esp config` command family. You never need to edit the file directly.

```bash
# Interactive wizard to configure ESP-IDF
analogdata-esp config idf

# Interactive wizard to configure AI provider
analogdata-esp config ai

# Print current config to stdout
analogdata-esp config show
```

---

## Next Steps

- [ESP-IDF Setup](idf-setup.md) — detailed walkthrough of the IDF configuration wizard
- [AI Providers](ai-providers.md) — step-by-step setup for Ollama, OpenAI, Anthropic, and Gemini
