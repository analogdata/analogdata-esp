# Windows Installation

---

## Installer (.exe) — Recommended

1. Go to the [GitHub Releases page](https://github.com/analogdata/analogdata-esp/releases/latest)
2. Download `analogdata-esp-setup.exe`
3. Run the installer and follow the setup wizard
4. The installer adds `analogdata-esp` to your `PATH` automatically

### Verify

Open a **new** terminal window (Command Prompt or PowerShell) and run:

```powershell
analogdata-esp --help
```

!!! important "Open a new terminal"
    The PATH update made by the installer only takes effect in terminal sessions opened **after** installation. Close and reopen any existing terminal windows.

### Uninstall

Go to **Settings → Apps → analogdata-esp → Uninstall** and follow the prompts.

Alternatively, use the uninstaller located at:

```
C:\Program Files\analogdata-esp\uninstall.exe
```

---

## winget (Planned)

Support for installing via `winget` is planned for a future release:

```powershell
# Not yet available — coming soon
winget install analogdata.analogdata-esp
```

---

## pip / pipx

If you have Python 3.10+ installed, you can install from PyPI.

```powershell
# pipx (recommended — runs in an isolated environment)
pipx install analogdata-esp

# pip (global install)
pip install analogdata-esp
```

Install `pipx` if needed:

```powershell
pip install pipx
python -m pipx ensurepath
```

Restart your terminal after running `ensurepath`.

### Uninstalling

```powershell
pipx uninstall analogdata-esp
```

---

## From Source

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone and install
git clone https://github.com/analogdata/analogdata-esp.git
cd analogdata-esp
uv sync
uv run analogdata-esp --help
```

See [Local Installation](../getting-started/local-install.md) for the full developer setup guide.

---

## Verifying PATH

If `analogdata-esp` is not found after installation, check that the install directory is in your PATH.

```powershell
# Check current PATH
$env:PATH -split ";"

# Add manually if needed (replace with your actual install path)
$env:PATH += ";C:\Program Files\analogdata-esp"
```

To make the PATH change permanent, add it through **System Properties → Environment Variables**.
