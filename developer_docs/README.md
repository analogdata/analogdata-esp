# analogdata-esp Developer Documentation

Everything you need to build, release, and distribute the CLI.

## Contents

| Document | What it covers |
|---|---|
| [rebuild.md](rebuild.md) | Rebuild the binary after code changes |
| [github-release.md](github-release.md) | Push to GitHub and create a versioned release |
| [homebrew-tap.md](homebrew-tap.md) | How Homebrew finds your package — tap setup and updates |
| [debian-apt.md](debian-apt.md) | How APT finds your package — .deb and custom repo setup |

## Quick reference

```bash
# Rebuild binary (after code changes)
uv run pyinstaller analogdata-esp.spec --noconfirm

# Tag and release
git tag v0.2.0
git push origin main --tags      # triggers GitHub Actions → builds all 3 platforms

# Run tests before releasing
uv run pytest tests/ -v
uv run pytest tests/ --cov=analogdata_esp --cov-report=term-missing
```

## Release checklist

- [ ] Bump version in `pyproject.toml` and `analogdata_esp/main.py`
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Binary works locally: `uv run pyinstaller analogdata-esp.spec --noconfirm && dist/analogdata-esp doctor`
- [ ] `git tag vX.Y.Z && git push origin main --tags`
- [ ] GitHub Actions completes — check the Actions tab
- [ ] Download macOS binary from release, update SHA256 in Homebrew formula
- [ ] Commit updated formula to `homebrew-tap` repo
- [ ] (Optional) Upload `.deb` to Packagecloud
