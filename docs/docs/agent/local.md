# Local Setup (Ollama + Gemma)

Running the agent locally means your code and build errors never leave your machine.

## Install Ollama

=== "macOS"
    ```bash
    brew install ollama
    ```

=== "Linux"
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```

=== "Windows"
    Download from [ollama.com](https://ollama.com) and run the installer.

## Pull Gemma 3 4B

```bash
ollama pull gemma3:4b
```

This downloads ~3GB. Run once and it's cached locally.

## Start Ollama

```bash
ollama serve
```

Run this in a separate terminal or add it to your startup items.

To verify it's running:
```bash
analogdata-esp doctor
# Ollama + Gemma   ✅ running   gemma3:4b
```

## Test it

```bash
analogdata-esp agent "what is the difference between xTaskCreate and xTaskCreatePinnedToCore"
```

## Keep Ollama running on startup (macOS)

```bash
# Add to your shell profile
echo 'ollama serve &>/dev/null &' >> ~/.zshrc
```

Or use the macOS launchd service that Ollama installs automatically via Homebrew.
