# AI Agent Overview

The `analogdata-esp agent` is an ESP-IDF-aware AI assistant built into the CLI.
It is designed around a **local-first** philosophy — your code and build errors
stay on your machine.

## Architecture

```
analogdata-esp agent "question"
        │
        ▼
  ┌─────────────────┐
  │  Context reader  │  reads sdkconfig, CMakeLists, build errors
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐     YES   ┌──────────────────────┐
  │ Ollama running? │ ─────────▶│ Gemma 3 4B (local)   │
  └────────┬────────┘           └──────────────────────┘
           │ NO
           ▼
  ┌─────────────────┐     YES   ┌──────────────────────┐
  │ GEMINI_API_KEY  │ ─────────▶│ Gemini API (cloud)   │
  │ set?            │           └──────────────────────┘
  └────────┬────────┘
           │ NO
           ▼
     Setup instructions
```

## System prompt

The agent is primed with deep ESP-IDF context:

- ESP-IDF v5.x API knowledge
- FreeRTOS patterns (tasks, queues, semaphores, event groups)
- Common ESP-IDF components: WiFi, BLE, MQTT, NVS, GPIO, UART, SPI, I2C
- CMake / sdkconfig / menuconfig
- Build error interpretation
- Flash and monitor troubleshooting

## Auto-context injection

Every question is enriched with your project context automatically:

```
Project: sensor_node
Target chip: esp32s3
ESP-IDF version: v5.5.3

Build error output:
  error: undefined reference to 'esp_wifi_init'
  ...

Question: why is this failing
```

This gives the model everything it needs without you having to copy-paste anything.

## Model choice

| Backend | Model | Speed | Privacy | Cost |
|---------|-------|-------|---------|------|
| Ollama (local) | Gemma 3 4B | ~2–5s first token | ✅ 100% local | Free |
| Gemini API | gemma-3-4b-it | ~1–2s first token | Cloud | Free tier available |

Gemma 3 4B was chosen for its strong performance on code and technical tasks
at a size that runs comfortably on Apple Silicon with 8GB RAM.
