# analogdata-esp doctor

Check your ESP-IDF environment and AI agent backends.

## Usage

```bash
analogdata-esp doctor
```

## What it checks

| Check | What it looks for |
|-------|------------------|
| ESP-IDF | Detects IDF path across Windsurf, EIM, manual installs |
| IDF version | Reads `version.txt` from IDF root |
| Python venv | ESP-IDF virtualenv at `~/.espressif/tools/python/` |
| xtensa-esp32-elf-gcc | Xtensa toolchain in PATH |
| cmake | CMake ≥ 3.16 |
| ninja | Ninja build system |
| git | Git for project init |
| Ollama + Gemma | Local AI backend status and loaded models |
| GEMINI_API_KEY | Cloud fallback key |

## Sample output

```
⚡ analogdata-esp doctor

  Check                  Status          Detail
  ─────────────────────────────────────────────────────────────
  ESP-IDF                ✅ found        ~/.espressifforwindsurf/v5.5.3/esp-idf
  IDF version            ✅              v5.5.3
  Python (venv)          ✅ found        ~/.espressif/tools/python/v5.5.3/venv/bin/python3
  xtensa-esp32-elf-gcc   ⚠ not in PATH  Source export.sh first
  cmake                  ✅              cmake version 3.31.6
  ninja                  ✅              /opt/homebrew/bin/ninja
  git                    ✅              git version 2.51.0
  Ollama + Gemma         ✅ running      gemma3:4b
  GEMINI_API_KEY         not set        Optional (Ollama is available)
```

## Common fixes

**xtensa-esp32-elf-gcc not in PATH**

The toolchain isn't in your shell PATH. This is normal — ESP-IDF manages it internally.
You only need it in PATH for direct terminal use. The VSCode/Windsurf extension handles it automatically.

To add it for terminal use:
```bash
source ~/.espressifforwindsurf/v5.5.3/esp-idf/export.sh
```

Or add an alias to `~/.zshrc`:
```bash
alias get_idf='source ~/.espressifforwindsurf/v5.5.3/esp-idf/export.sh'
```

**Ollama not running**

```bash
ollama serve          # start in background
ollama pull gemma3:4b # first time only
```

**ESP-IDF not found**

Install via EIM (recommended for v6.0+) or manual clone:
```bash
mkdir ~/esp && cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && git checkout v5.4.2
./install.sh esp32
```
