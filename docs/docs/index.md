# analogdata-esp

**ESP-IDF CLI for embedded engineers** — by [Analog Data](https://analogdata.io)

```bash
pip install analogdata-esp
```

---

## What it does

`analogdata-esp` is a command-line tool that eliminates boilerplate when working with ESP-IDF. It scaffolds production-ready projects in seconds and gives you an AI agent that understands your build errors.

```bash
# Create a new ESP32-S3 project
analogdata-esp new sensor_node --target esp32s3

# Ask the AI agent about a build error (auto-reads your errors)
analogdata-esp agent "why is my FreeRTOS heap failing"

# Interactive chat mode
analogdata-esp agent --chat

# Health check your environment
analogdata-esp doctor
```

---

## Features

| Feature | Description |
|---------|-------------|
| `new` | Scaffold ESP-IDF projects with `.vscode`, `.clangd`, CMake, and git |
| `agent` | AI assistant — local Gemma 3 4B or Gemini API fallback |
| `doctor` | Diagnose ESP-IDF, toolchain, and AI backend health |

---

## AI Agent

The agent runs **locally first** using [Ollama](https://ollama.com) + Gemma 3 4B — your code never leaves your machine. If Ollama isn't running, it falls back to the Gemini API.

It **automatically reads your build errors** — no copy-pasting required.

```
analogdata-esp agent "explain this linker error"
📋 Auto-attached build errors (12 lines)

── agent ───────────────────────────────────
The linker error is caused by...
```

---

## Quick Install

```bash
pip install analogdata-esp

# For local AI (recommended)
brew install ollama
ollama pull gemma3:4b
ollama serve
```
