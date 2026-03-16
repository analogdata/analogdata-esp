# analogdata-esp

> ESP-IDF CLI for embedded engineers — by [Analog Data](https://analogdata.io)

Project scaffolding, AI agent, build/flash/monitor, and environment health checks — all in one tool. No Python knowledge required.

---

## Installation

### macOS (Homebrew) — recommended

```bash
brew tap analogdata/tap
brew install analogdata-esp
```

### From source (development)

```bash
git clone https://github.com/analogdata/analogdata-esp
cd analogdata-esp
uv sync
uv run analogdata-esp
```

**Requirements:** macOS · ESP-IDF v5.x installed via the official installer

---

## Quick Start

Running `analogdata-esp` with no arguments opens the interactive shell:

```
╭──────────────────────────────────────────────────────────────────╮
│  Analog Data — ESP-IDF CLI                                       │
│                                                                  │
│  new <name>          Scaffold a new ESP32 project                │
│  build               Build the current project                   │
│  flash               Flash to connected device                   │
│  monitor             Open serial monitor                         │
│  agent <question>    Ask the AI assistant                        │
│  doctor              Check your ESP-IDF environment              │
│  config              Configure providers and settings            │
│  config vscode       Fix VS Code / ESP-IDF extension settings    │
│  help                Show this menu                              │
│  exit                Quit                                        │
╰──────────────────────────────────────────────────────────────────╯
analogdata-esp>
```

---

## Commands

### `new` — Scaffold a project

```bash
# Creates blink/ with CMakeLists.txt, main/blink.c, .vscode/, .clangd, .gitignore
analogdata-esp new blink

# Target a specific chip
analogdata-esp new sensor_node --target esp32s3
analogdata-esp new motor_ctrl  --target esp32c3

# Inside the interactive shell:
analogdata-esp> new blink --target esp32s3
```

Generated project structure:

```
blink/
├── CMakeLists.txt          # Top-level CMake (IDF component)
├── main/
│   ├── CMakeLists.txt      # Component registration
│   └── blink.c             # Starter source file
├── .vscode/
│   └── settings.json       # ESP-IDF extension paths (auto-detected)
├── .clangd                 # IntelliSense config pointing to IDF headers
└── .gitignore
```

---

### `build` / `flash` / `monitor` — Build & deploy

```bash
# Build the project in the current directory
analogdata-esp build

# Flash to the connected ESP32 (auto-detects port)
analogdata-esp flash

# Open the serial monitor (Ctrl+] to exit)
analogdata-esp monitor

# Build + flash + monitor in one step
analogdata-esp flash --monitor

# Inside the interactive shell:
analogdata-esp> build
analogdata-esp> flash
analogdata-esp> monitor
```

---

### `agent` — AI assistant

Ask questions about your ESP-IDF project. The agent reads your build errors, `CMakeLists.txt`, target chip, and `sdkconfig` automatically — no copy-pasting needed.

```bash
# One-shot question
analogdata-esp agent "why is my FreeRTOS task crashing"

# After a failed build — auto-attaches the error log
idf.py build   # fails
analogdata-esp agent "fix this"
# 📋 Auto-attached build errors (8 lines)
# ── agent ─────────────────────────────────────────────────────────────
# The error is in app_main.c line 42 — you're calling gpio_set_level()
# before gpio_config()...

# Interactive chat mode (multi-turn conversation)
analogdata-esp agent --chat

# Agent mode — lets the AI run idf.py commands on your behalf
analogdata-esp agent --agent "set up PWM on GPIO 18 and build"
```

#### AI providers (in order of preference)

| Provider | Setup | Cost |
|----------|-------|------|
| **Ollama** (local) | `brew install ollama && ollama pull gemma3:4b && ollama serve` | Free, offline |
| **Gemini API** | `export GEMINI_API_KEY=your_key` — get from [aistudio.google.com](https://aistudio.google.com) | Free tier available |
| **OpenAI** | `export OPENAI_API_KEY=your_key` | Paid |
| **Anthropic** | `export ANTHROPIC_API_KEY=your_key` | Paid |

Configure interactively:

```bash
analogdata-esp config
```

---

### `doctor` — Environment health check

Verifies your entire ESP-IDF setup and reports any problems:

```bash
analogdata-esp doctor
```

```
✔  IDF_PATH       /Users/you/.espressif/frameworks/esp-idf-v5.3
✔  xtensa-esp32-elf-gcc  14.2.0
✔  esptool.py     4.7.0
✔  CMake          3.28.0
✔  Ninja          1.11.1
✔  Python (IDF)   3.11.9
✔  Ollama         running  (gemma3:4b available)
```

---

### `config` — Settings

```bash
# Full interactive config wizard
analogdata-esp config

# Fix .vscode/settings.json for the official ESP-IDF VS Code extension
# Run this inside your project directory
analogdata-esp config vscode
```

`config vscode` writes the correct `idf.espIdfPath`, `idf.toolsPath`, and `idf.pythonBinPath` keys into `.vscode/settings.json` so the VS Code ESP-IDF extension finds your installation. Run it once per project, or after moving your IDF installation.

---

## AI Agent Details

### How context is attached automatically

Every query sent to the AI includes:

- **Target chip** — read from `sdkconfig` (`CONFIG_IDF_TARGET`)
- **Project name** — read from `CMakeLists.txt` (`project(...)`)
- **Recent build errors** — read from `build/log/idf_py_stderr_output`
- **Conversation history** — maintained across turns in `--chat` mode

### Agent mode (tool use)

With `--agent`, the AI can execute `idf.py` commands directly:

```bash
analogdata-esp agent --agent "enable CONFIG_FREERTOS_USE_TRACE_FACILITY and rebuild"
# Tool call: idf.py menuconfig  → sets the flag
# Tool call: idf.py build       → rebuilds
# Build succeeded in 14s.
```

---

## VS Code Integration

If the ESP-IDF extension shows `command 'espidf.buildDevice' not found`:

```bash
cd your-project
analogdata-esp config vscode
```

This regenerates `.vscode/settings.json` with paths detected from your local IDF installation. Reload VS Code after running.

---

## Updating

```bash
brew upgrade analogdata-esp
analogdata-esp doctor   # confirm new version works
```

---

## License

MIT · Built by [Analog Data](https://analogdata.io)
