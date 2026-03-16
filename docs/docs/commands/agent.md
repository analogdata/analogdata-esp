# analogdata-esp agent

AI assistant for ESP-IDF development. Runs locally with Ollama + Gemma 3 4B,
falls back to Gemini API if Ollama is not available.

## Usage

```bash
analogdata-esp agent [QUESTION] [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `QUESTION` | Question to ask. Omit to enter interactive chat mode. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--chat`, `-c` | `false` | Start interactive chat session |
| `--no-context` | `false` | Don't auto-read project context and build errors |
| `--dir`, `-d` | `cwd` | Project directory to read context from |

## Examples

```bash
# Single question
analogdata-esp agent "why is my FreeRTOS task crashing"

# Agent auto-reads your build errors
analogdata-esp agent "explain this linker error"
# 📋 Auto-attached build errors (8 lines)

# Interactive chat
analogdata-esp agent --chat

# Ask about a different project
analogdata-esp agent "why is heap allocation failing" --dir ~/esp/my_project

# Disable auto context
analogdata-esp agent "what is portTICK_PERIOD_MS" --no-context
```

## Auto context

By default, the agent automatically reads:

- **Project name** from `CMakeLists.txt`
- **Target chip** from `sdkconfig`
- **IDF version** from `sdkconfig`
- **Build errors** from `build/log/idf_py_stderr_output`

This means you can just run:
```bash
idf.py build        # fails with an error
analogdata-esp agent "fix this"   # agent already knows the error
```

## Chat mode slash commands

When running `--chat`, these commands are available:

| Command | Description |
|---------|-------------|
| `/exit` | Exit chat |
| `/clear` | Clear screen |
| `/context` | Show detected project context |
| `/errors` | Show latest build errors |

## Backend selection

```
Is Ollama running + gemma3:4b loaded?
  ✅ YES → local inference (private, free, ~2s first token)
  ❌ NO  → is GEMINI_API_KEY set?
              ✅ YES → Gemini API (cloud, requires internet)
              ❌ NO  → shows setup instructions
```

See [AI Agent — Local Setup](../agent/local.md) and [Cloud Setup](../agent/cloud.md).
