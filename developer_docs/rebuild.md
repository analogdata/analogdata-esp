# Rebuilding the Binary

Every time you change source code and want a fresh standalone binary, follow this.

---

## Prerequisites

These only need to be installed once:

```bash
# uv (package manager) — already set up if you followed local-install.md
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all project deps including pyinstaller
cd /path/to/analogdata-esp
uv sync --dev
```

---

## Rebuild (one command)

```bash
cd /Users/rajathkumar/analogdata-esp
uv run pyinstaller analogdata-esp.spec --noconfirm
```

Output: `dist/analogdata-esp`
Build artifacts (safe to ignore/delete): `build/`

---

## What the spec does

`analogdata-esp.spec` tells PyInstaller to:

1. Start from `analogdata_esp/main.py`
2. Bundle **all Python dependencies** (typer, rich, httpx, jinja2, anthropic, openai, etc.)
3. Bundle the **`templates/`** directory as data (needed by `analogdata-esp new`)
4. Produce a single self-contained binary — no Python required on the target machine

The `get_template_dir()` function in `core/config.py` handles the frozen path automatically via `sys._MEIPASS`.

---

## Test the binary immediately

```bash
# Basic smoke test
dist/analogdata-esp --help
dist/analogdata-esp doctor

# Full end-to-end: scaffold a project
dist/analogdata-esp new smoke_test --target esp32
ls smoke_test/
rm -rf smoke_test/

# Config
dist/analogdata-esp config
```

If `dist/analogdata-esp doctor` shows the ESP-IDF path and Ollama status correctly, the binary is good.

---

## Using the build script (wraps PyInstaller + platform packaging)

```bash
# Auto-detects your platform
./scripts/build-local.sh

# Or explicitly
./scripts/build-local.sh brew    # macOS — produces dist/analogdata-esp
./scripts/build-local.sh deb     # Linux — produces dist/analogdata-esp_X.Y.Z_amd64.deb
./scripts/build-local.sh win     # Windows — produces dist/analogdata-esp-X.Y.Z-setup.exe
```

---

## Install the rebuilt binary on your Mac

```bash
sudo cp dist/analogdata-esp /usr/local/bin/analogdata-esp
sudo xattr -c /usr/local/bin/analogdata-esp   # clear Gatekeeper quarantine
analogdata-esp --help
```

To uninstall: `sudo rm /usr/local/bin/analogdata-esp`

---

## Binary size and build time

| Stage | Typical time (M2 Mac) |
|---|---|
| First build | ~45–90 seconds |
| Rebuild (cached) | ~20–40 seconds |
| Binary size | ~25–40 MB |

The binary is large because it contains a full CPython interpreter and all libraries. This is normal for PyInstaller.

---

## Troubleshooting

### `ModuleNotFoundError` at runtime
A dependency is missing from `hidden_imports` in the spec. Add it to `analogdata-esp.spec`:
```python
hidden_imports = [
    ...
    "your.missing.module",
]
```
Then rebuild.

### Templates not found
Check that `datas` in the spec includes `("templates", "templates")`. Verify after build:
```bash
# Inspect the bundle contents
pyinstaller --noconfirm analogdata-esp.spec
ls build/analogdata-esp/analogdata-esp/templates/
```

### `xcrun: error` on macOS (code signing)
Install Xcode command line tools:
```bash
xcode-select --install
```

### Gatekeeper blocks the binary
```bash
sudo xattr -c /usr/local/bin/analogdata-esp
# or for the dist/ binary:
xattr -c dist/analogdata-esp
```
