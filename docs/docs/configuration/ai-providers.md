# AI Provider Configuration

`analogdata-esp` supports four AI backends. You can switch between them at any time by re-running `analogdata-esp config ai`.

---

## Ollama (Local — Recommended)

Ollama runs models entirely on your machine. No API key or internet connection is required after the initial model download.

### 1. Install Ollama

=== "macOS"

    ```bash
    brew install ollama
    ```

=== "Ubuntu / Debian"

    ```bash
    curl -fsSL https://ollama.ai/install.sh | sh
    ```

=== "Windows / Other"

    Download the installer from [ollama.ai](https://ollama.ai).

### 2. Start the Ollama server

```bash
ollama serve
```

Leave this running in a terminal (or configure it as a system service).

### 3. Pull a model

```bash
# Lightweight, fast (recommended for most machines)
ollama pull gemma3:4b

# Even lighter
ollama pull gemma3:1b

# Other popular choices
ollama pull llama3.2
ollama pull mistral
ollama pull codellama
ollama pull phi3
ollama pull deepseek-coder
```

### 4. Configure analogdata-esp

```bash
analogdata-esp config ai
```

Select **Ollama** when prompted, then enter the model name you pulled (e.g. `gemma3:4b`).

### Supported models

| Model | Notes |
|---|---|
| `gemma3:4b` | Good balance of speed and quality |
| `gemma3:1b` | Fastest; suitable for low-RAM machines |
| `llama3.2` | Strong general-purpose model |
| `mistral` | Good at instruction following |
| `codellama` | Optimised for code generation |
| `phi3` | Microsoft small model, very fast |
| `deepseek-coder` | Excellent for embedded/systems code |

---

## OpenAI

### 1. Get an API key

Create an account and generate a key at [platform.openai.com](https://platform.openai.com/api-keys).

### 2. Configure analogdata-esp

```bash
analogdata-esp config ai
```

Select **OpenAI**, paste your API key when prompted, and choose a model (default: `gpt-4o`).

Alternatively, set the key as an environment variable (it will take precedence over the saved config):

```bash
export OPENAI_API_KEY=sk-...
```

### Supported models

| Model | Notes |
|---|---|
| `gpt-4o` | Default; best quality |
| `gpt-4-turbo` | Slightly older, still high quality |
| `gpt-3.5-turbo` | Fastest and cheapest |

---

## Anthropic (Claude)

### 1. Get an API key

Create an account and generate a key at [console.anthropic.com](https://console.anthropic.com).

### 2. Configure analogdata-esp

```bash
analogdata-esp config ai
```

Select **Anthropic**, paste your API key when prompted, and choose a model (default: `claude-3-5-sonnet-20241022`).

Alternatively, set the key as an environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Supported models

| Model | Notes |
|---|---|
| `claude-3-5-sonnet-20241022` | Default; excellent reasoning and code |
| `claude-3-haiku-20240307` | Fastest and most cost-efficient |
| `claude-opus-4-6` | Most capable Claude model |

---

## Gemini

Google Gemini offers a **free tier** which is sufficient for most personal use.

### 1. Get an API key

Visit [aistudio.google.com](https://aistudio.google.com) and click **Get API key**. No billing setup required for the free tier.

### 2. Configure analogdata-esp

```bash
analogdata-esp config ai
```

Select **Gemini**, paste your API key when prompted, and choose a model (default: `gemini-2.0-flash`).

Alternatively, set the key as an environment variable:

```bash
export GEMINI_API_KEY=AIza...
```

### Supported models

| Model | Notes |
|---|---|
| `gemini-2.0-flash` | Default; fast and capable |
| `gemini-1.5-pro` | Higher quality; slower |

---

## Switching Providers

Run the configuration wizard again at any time to switch to a different provider:

```bash
analogdata-esp config ai
```

The new selection overwrites the `[ai]` section in `config.toml`.

---

## Environment Variable Priority

Environment variables always override values in `config.toml`. This is useful for CI/CD or per-project overrides:

| Variable | Provider |
|---|---|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GEMINI_API_KEY` | Gemini |

Ollama does not require an API key.

---

## Verifying the Configuration

```bash
analogdata-esp doctor
```

Expected output for a correctly configured provider:

```
[OK] AI provider: ollama (gemma3:4b)
[OK] Ollama server reachable at http://localhost:11434
```
