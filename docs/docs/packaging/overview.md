# Packaging Overview

`analogdata-esp` is distributed as pre-built packages for all major platforms. This page explains the available distribution methods and how the release pipeline works.

---

## Distribution Methods

| Method | Platform | Recommended for |
|---|---|---|
| Homebrew | macOS | End users on macOS |
| `.deb` package | Debian / Ubuntu | End users on Linux |
| `.exe` installer | Windows | End users on Windows |
| `pip` / `pipx` | All | Python developers |
| Source (uv) | All | Contributors / developers |

---

## Platform Guides

- [macOS Installation](macos.md)
- [Linux Installation](linux.md)
- [Windows Installation](windows.md)

---

## How the Release Pipeline Works

Releases are fully automated via **GitHub Actions**. The pipeline is triggered by pushing a version tag.

```
git tag v0.1.0
git push --tags
```

This kicks off the following jobs in parallel:

```
Tag pushed
    │
    ├── build-macos
    │       PyInstaller → analogdata-esp (ARM64 + x86_64)
    │       → Homebrew formula update
    │
    ├── build-linux
    │       PyInstaller → analogdata-esp (x86_64)
    │       → .deb package (dpkg-deb)
    │
    └── build-windows
            PyInstaller → analogdata-esp.exe
            → NSIS installer (.exe)
```

After all builds succeed, a **GitHub Release** is created automatically with:

- macOS binary (universal)
- Linux binary
- Linux `.deb` package
- Windows `.exe` installer
- Source distribution (`.tar.gz` and `.whl`) pushed to PyPI

### PyInstaller

Each platform build uses [PyInstaller](https://pyinstaller.org) to bundle the Python interpreter and all dependencies into a single executable. The result is a binary that runs without requiring Python to be installed on the target machine.

### Versioning

The version is read from the git tag. Tags must follow [SemVer](https://semver.org): `vMAJOR.MINOR.PATCH` (e.g. `v0.1.0`, `v1.2.3`).

---

## Triggering a Release

```bash
# Create and push a tag — replace with the actual version
git tag v0.1.0
git push --tags
```

!!! warning "Tag format"
    Tags must start with `v` and follow SemVer. Tags like `0.1.0` or `release-1` will not trigger the release workflow.

Monitor the pipeline at:
`https://github.com/analogdata/analogdata-esp/actions`

---

## pip / pipx

For users who already have Python installed, the package is also available on PyPI:

```bash
# pipx (isolated environment — recommended)
pipx install analogdata-esp

# pip (global install)
pip install analogdata-esp
```

PyPI releases are published automatically as part of the same GitHub Actions pipeline.
