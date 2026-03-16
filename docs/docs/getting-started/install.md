# Installation

## Requirements

- Python 3.10+
- ESP-IDF v5.x installed (via EIM or manual clone)
- macOS, Linux, or Windows

## Install

```bash
pip install analogdata-esp
```

Verify:
```bash
analogdata-esp --help
```

## AI Agent Setup

### Option A — Local (Recommended, Private)

```bash
# Install Ollama
brew install ollama          # macOS
# or: curl -fsSL https://ollama.com/install.sh | sh  (Linux)

# Pull Gemma 3 4B model (~3GB)
ollama pull gemma3:4b

# Start Ollama server (runs in background)
ollama serve
```

The agent will automatically use Ollama when it's running.

### Option B — Gemini API (Cloud Fallback)

```bash
export GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).

Add to `~/.zshrc` to persist:
```bash
echo 'export GEMINI_API_KEY=your_key' >> ~/.zshrc
```

### How fallback works

```
analogdata-esp agent "..."
       ↓
Is Ollama running + gemma3:4b available?
  YES → runs locally (private, free)
  NO  → is GEMINI_API_KEY set?
          YES → uses Gemini API
          NO  → shows setup instructions
```

## Run doctor

After installation, run the health check:

```bash
analogdata-esp doctor
```

All green means you're ready to build.
