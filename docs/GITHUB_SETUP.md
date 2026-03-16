# GitHub Setup Guide for analogdata-esp

Two GitHub repositories are required:

| Repo | Purpose |
|------|---------|
| `rajathkumar/analogdata-esp` | Source code (this repo) |
| `rajathkumar/homebrew-analogdata-esp` | Homebrew tap formula |

---

## Repo 1 — Source Code: `rajathkumar/analogdata-esp`

1. Create on GitHub: **github.com/new** → Name: `analogdata-esp` → Public → Create

2. Push the source:
```bash
cd ~/analogdata-esp
git init          # skip if already a git repo
git add .
git commit -m "Initial release v0.1.0"
git remote add origin https://github.com/rajathkumar/analogdata-esp.git
git push -u origin main
```

---

## Repo 2 — Homebrew Tap: `rajathkumar/homebrew-analogdata-esp`

> **The name MUST be `homebrew-analogdata-esp`** — Homebrew requires the prefix `homebrew-`.

1. Create on GitHub: **github.com/new** → Name: `homebrew-analogdata-esp` → Public → Create

2. Push the formula (it already exists locally):
```bash
cd /opt/homebrew/Library/Taps/rajathkumar/homebrew-analogdata-esp
git remote add origin https://github.com/rajathkumar/homebrew-analogdata-esp.git
git add Formula/analogdata-esp.rb
git commit -m "Add analogdata-esp formula v0.1.0"
git push -u origin main
```

---

## Release Workflow (every new version)

```bash
# 1. Bump version in pyproject.toml

# 2. Build the release tarball
cd ~/analogdata-esp
./packaging/build_release.sh v0.x.x

# 3. Create GitHub release and upload the tarball
gh release create v0.x.x \
  dist/analogdata-esp-macos-arm64-v0.x.x.tar.gz \
  --title "v0.x.x" --notes "Release notes here"

# 4. Update the formula with the new URL and SHA256
# (build_release.sh prints the SHA256 at the end)
# Edit /opt/homebrew/Library/Taps/rajathkumar/homebrew-analogdata-esp/Formula/analogdata-esp.rb:
#   url    "https://github.com/rajathkumar/analogdata-esp/releases/download/v0.x.x/analogdata-esp-macos-arm64-v0.x.x.tar.gz"
#   sha256 "<printed by build_release.sh>"

# 5. Push the updated formula
cd /opt/homebrew/Library/Taps/rajathkumar/homebrew-analogdata-esp
git add Formula/analogdata-esp.rb
git commit -m "Release v0.x.x"
git push
```

---

## How Others Install

```bash
brew tap rajathkumar/analogdata-esp
brew install analogdata-esp
```

That's it. Homebrew fetches the formula from `homebrew-analogdata-esp`,
downloads the tarball from the GitHub release, and installs the binary.

---

## Directory Structure Reference

```
~/analogdata-esp/                         ← source repo (rajathkumar/analogdata-esp)
  analogdata_esp/                         ← Python package
  templates/                              ← ESP-IDF project templates
  packaging/
    build_release.sh                      ← builds tarball + prints SHA256
    homebrew/analogdata-esp.rb            ← formula copy (for reference)
  dist/
    analogdata-esp-macos-arm64-v0.x.x.tar.gz   ← release tarball
    analogdata-esp-macos-arm64-v0.x.x.tar.gz.sha256

/opt/homebrew/Library/Taps/rajathkumar/homebrew-analogdata-esp/
  Formula/analogdata-esp.rb              ← live formula (rajathkumar/homebrew-analogdata-esp)
```
