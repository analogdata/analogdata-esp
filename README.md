# analogdata-esp

> ESP-IDF CLI for embedded engineers — by [Analog Data](https://analogdata.io)

```bash
pip install analogdata-esp
```

---

## Commands

```bash
# Scaffold a new project (with .vscode, .clangd, CMake, git)
analogdata-esp new blink
analogdata-esp new sensor_node --target esp32s3

# AI agent — local Gemma 3 4B or Gemini API fallback
analogdata-esp agent "why is my FreeRTOS task crashing"
analogdata-esp agent --chat

# Environment health check
analogdata-esp doctor
```

## AI Agent

Runs locally with **Ollama + Gemma 3 4B** — your code stays on your machine.
Falls back to **Gemini API** if Ollama isn't running.

Auto-reads your build errors. No copy-pasting.

```bash
idf.py build   # fails
analogdata-esp agent "fix this"
# 📋 Auto-attached build errors (8 lines)
# ── agent ──────────────────────────────
# The error is caused by...
```

### Setup local AI

```bash
brew install ollama
ollama pull gemma3:4b
ollama serve
```

### Setup cloud fallback

```bash
export GEMINI_API_KEY=your_key   # from aistudio.google.com
```

---

## Installation

```bash
pip install analogdata-esp
analogdata-esp doctor   # verify setup
```

**Requirements:** Python 3.10+ · ESP-IDF v5.x

---

## Docs

Full documentation at [docs.analogdata.io/esp-cli](https://docs.analogdata.io/esp-cli)

---

## License

MIT · Built by [Analog Data](https://analogdata.io)
