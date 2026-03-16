# Testing

This guide covers everything you need to know about running, writing, and extending the test suite for `analogdata-esp`.

---

## Test Structure

All tests live in the `tests/` directory at the repository root:

```
tests/
├── conftest.py              # Shared fixtures (tmp_config_dir, tmp_project_dir, fake_idf_dir)
├── test_settings.py         # Config read/write, TOML parsing, env var overrides
├── test_doctor.py           # Doctor command — IDF detection, provider health checks
├── test_new.py              # Project scaffolding — template generation, file output
├── test_agent.py            # Agent command — AI provider dispatch, prompt building
└── test_cli.py              # Top-level CLI — --help, --version, error handling
```

The test suite uses [pytest](https://docs.pytest.org) with the following plugins:

| Plugin | Purpose |
|---|---|
| `pytest-asyncio` | Running async test functions |
| `pytest-cov` | Coverage measurement |

---

## Running Tests

### Run all tests

```bash
uv run pytest tests/ -v
```

### Run a single file

```bash
uv run pytest tests/test_settings.py -v
```

### Run a single test by name

```bash
uv run pytest tests/test_settings.py::test_save_and_reload_config -v
```

### Run tests matching a keyword

```bash
uv run pytest tests/ -k "idf" -v
```

---

## Coverage

### Terminal coverage report

```bash
uv run pytest tests/ --cov=analogdata_esp --cov-report=term-missing
```

The `term-missing` option prints the line numbers that are not covered, making it easy to see exactly what needs tests.

### HTML coverage report

```bash
uv run pytest tests/ --cov=analogdata_esp --cov-report=term-missing --cov-report=html
```

Open the report:

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

The command exits with code 1 if coverage is below 80%. This threshold is also enforced in CI.

---

## Shared Fixtures

Fixtures are defined in `tests/conftest.py` and available to all test files automatically.

### `tmp_config_dir`

Provides a temporary directory and patches `analogdata_esp.settings.CONFIG_DIR` to point to it. Ensures tests never touch your real `~/.config/analogdata-esp/` directory.

```python
def test_saves_config(tmp_config_dir):
    settings = Settings()
    settings.idf.path = "/tmp/esp-idf"
    settings.save()
    assert (tmp_config_dir / "config.toml").exists()
```

### `tmp_project_dir`

Returns a `pathlib.Path` pointing to a freshly created empty temporary directory, suitable for testing project generation output.

```python
def test_new_creates_cmake(tmp_project_dir):
    create_project("my_project", output_dir=tmp_project_dir)
    assert (tmp_project_dir / "my_project" / "CMakeLists.txt").exists()
```

### `fake_idf_dir`

Creates a minimal fake ESP-IDF directory tree (with `idf.py`, `tools/`, `components/`) inside a temp directory. Useful for testing IDF detection logic without a real installation.

```python
def test_detects_idf(fake_idf_dir):
    result = detect_idf_installations()
    assert any(str(fake_idf_dir) in str(p) for p in result)
```

---

## Writing New Tests

### File and naming conventions

- Test files must be named `test_*.py`
- Test functions must be named `test_*`
- Group related tests into the same file as the module they test

### Example: synchronous test

```python
# tests/test_settings.py

def test_default_provider_is_ollama(tmp_config_dir):
    settings = Settings()
    assert settings.ai.provider == "ollama"
```

### Example: async test

Use `pytest-asyncio` for testing async functions. Mark individual tests or entire modules:

```python
# tests/test_agent.py
import pytest

@pytest.mark.asyncio
async def test_ollama_returns_response(tmp_config_dir):
    response = await query_ollama(prompt="Hello", model="gemma3:4b")
    assert isinstance(response, str)
    assert len(response) > 0
```

To mark an entire module as async by default, add this at the top of the file:

```python
pytestmark = pytest.mark.asyncio
```

---

## Mocking HTTP Requests

Use `unittest.mock.AsyncMock` and `pytest.monkeypatch` (or `unittest.mock.patch`) to mock `httpx` calls without making real network requests.

### Example: mocking an Ollama HTTP call

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ollama_mock():
    mock_response = AsyncMock()
    mock_response.json.return_value = {"response": "Hello from mock"}
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        from analogdata_esp.providers.ollama import OllamaProvider
        provider = OllamaProvider(model="gemma3:4b")
        result = await provider.complete("Say hello")

    assert result == "Hello from mock"
```

---

## Continuous Integration

Tests run automatically on every push and pull request via **GitHub Actions**.

The CI matrix covers:

| OS | Python |
|---|---|
| ubuntu-latest | 3.10, 3.11, 3.12 |
| macos-latest | 3.11 |
| windows-latest | 3.11 |

The workflow file is located at `.github/workflows/test.yml`. A coverage report is uploaded as a workflow artifact on each run.

Failed tests block merging of pull requests.
