# Local Installation & Development Setup

This guide covers installing `analogdata-esp` from source for local development, running tests, building binaries, and serving the documentation site locally.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10+** — check with `python3 --version`
- **[uv](https://docs.astral.sh/uv/)** — fast Python package and project manager
- **git** — for cloning the repository

Install `uv` if you do not have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Clone the Repository

```bash
git clone https://github.com/analogdata/analogdata-esp.git
cd analogdata-esp
```

---

## Install All Dependencies

Use `uv sync` with the `--dev` flag to install the project and all development dependencies (testing, linting, docs):

```bash
uv sync --dev
```

This creates a virtual environment in `.venv/` and installs everything specified in `pyproject.toml`.

---

## Verify the Installation

After syncing, verify the CLI is available:

```bash
analogdata-esp --help
```

You should see the top-level help output listing all available commands.

---

## Check Your Environment

Run the `doctor` command to verify that ESP-IDF and AI provider dependencies are configured correctly:

```bash
analogdata-esp doctor
```

The doctor command checks:

- ESP-IDF installation and tools path
- Active AI provider configuration
- Connectivity to the AI provider (for cloud providers)
- Python environment health

---

## Running Tests

### Run all tests

```bash
uv run pytest tests/ -v
```

### Run a single test file

```bash
uv run pytest tests/test_settings.py -v
```

### Run with coverage (terminal report)

```bash
uv run pytest tests/ --cov=analogdata_esp --cov-report=term-missing
```

### Run with coverage (HTML report)

```bash
uv run pytest tests/ --cov=analogdata_esp --cov-report=term-missing --cov-report=html
```

### Open the HTML coverage report

=== "macOS"

    ```bash
    open htmlcov/index.html
    ```

=== "Linux"

    ```bash
    xdg-open htmlcov/index.html
    ```

=== "Windows"

    ```powershell
    start htmlcov/index.html
    ```

### Enforce a coverage threshold

```bash
uv run pytest tests/ --cov=analogdata_esp --cov-fail-under=80
```

The command exits with a non-zero code if coverage falls below 80%.

---

## Building the Binary Locally

A helper script wraps PyInstaller to produce a self-contained binary for your platform:

```bash
./scripts/build-local.sh
```

The binary is written to `dist/analogdata-esp` (or `dist/analogdata-esp.exe` on Windows).

### Test the binary

```bash
dist/analogdata-esp --help
```

This binary has no dependency on the project's virtual environment and can be distributed as a standalone executable.

---

## Running the Documentation Site Locally

The documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To serve it with live-reload:

```bash
cd docs
uv run mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. Changes to any `.md` file are reflected immediately without restarting.

To build a static site:

```bash
cd docs
uv run mkdocs build
```

The output is written to `docs/site/`.
