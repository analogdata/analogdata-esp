# GitHub — First Push and Releasing

---

## Part 1: First-time GitHub setup

### 1. Create the repository on GitHub

Go to https://github.com/new and create a repo named `analogdata-esp` under your org/account.
- Visibility: Public (required for free Homebrew tap + Packagecloud)
- Do NOT initialize with README (you already have one)

### 2. Add the remote and push

```bash
cd /Users/rajathkumar/analogdata-esp

# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit — analogdata-esp v0.1.0"

# Add your GitHub remote
git remote add origin https://github.com/analogdata/analogdata-esp.git
# or with SSH:
git remote add origin git@github.com:analogdata/analogdata-esp.git

# Push
git push -u origin main
```

### 3. Configure GitHub Actions permissions

In your repo on GitHub:
- **Settings → Actions → General → Workflow permissions**
- Set to: **Read and write permissions**
- Check: **Allow GitHub Actions to create and approve pull requests**

### 4. Set up PyPI Trusted Publisher (for `pip install analogdata-esp`)

Go to https://pypi.org/manage/account/publishing/ and add:
- PyPI project name: `analogdata-esp`
- GitHub owner: `analogdata` (your org/username)
- GitHub repo: `analogdata-esp`
- Workflow filename: `release.yml`
- Environment name: `pypi`

Then in your GitHub repo:
- **Settings → Environments → New environment** → name it `pypi`

---

## Part 2: Releasing a new version

### Step 1 — Bump the version

Edit `pyproject.toml`:
```toml
[project]
version = "0.2.0"   # ← change this
```

Edit `analogdata_esp/main.py`:
```python
"[bold cyan]analogdata-esp[/bold cyan]  v0.2.0\n"  # ← change this
```

### Step 2 — Run tests

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=analogdata_esp --cov-fail-under=80
```

### Step 3 — Commit

```bash
git add pyproject.toml analogdata_esp/main.py
git commit -m "chore: bump version to v0.2.0"
git push
```

### Step 4 — Tag and push the tag

```bash
git tag v0.2.0
git push origin v0.2.0
```

**This is what triggers the release pipeline.** GitHub Actions detects the `v*.*.*` tag and automatically:

1. Builds the macOS binary (on `macos-14` runner)
2. Builds the Linux binary + `.deb` package (on `ubuntu-22.04` runner)
3. Builds the Windows binary + NSIS `.exe` installer (on `windows-2022` runner)
4. Creates a GitHub Release with all artifacts attached
5. Publishes the wheel to PyPI

---

## Part 3: What GitHub Actions does (`.github/workflows/release.yml`)

```
git push tag v0.2.0
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  GitHub Actions: release.yml                          │
│                                                       │
│  build (matrix — runs in parallel)                    │
│  ├── ubuntu-22.04                                     │
│  │   ├── uv sync --dev                                │
│  │   ├── pyinstaller analogdata-esp.spec              │
│  │   └── dpkg-deb → analogdata-esp_0.2.0_amd64.deb   │
│  │                                                    │
│  ├── macos-14 (Apple Silicon)                         │
│  │   ├── uv sync --dev                                │
│  │   └── pyinstaller → analogdata-esp-macos-arm64     │
│  │                                                    │
│  └── windows-2022                                     │
│      ├── uv sync --dev                                │
│      ├── pyinstaller → analogdata-esp.exe             │
│      └── makensis → analogdata-esp-0.2.0-setup.exe    │
│                                                       │
│  release (after all builds pass)                      │
│  └── softprops/action-gh-release                      │
│      └── Creates GitHub Release v0.2.0 with:          │
│          ├── analogdata-esp-macos-arm64               │
│          ├── analogdata-esp-linux-x86_64              │
│          ├── analogdata-esp_0.2.0_amd64.deb           │
│          └── analogdata-esp-0.2.0-setup.exe           │
│                                                       │
│  pypi (after builds pass)                             │
│  └── hatch build → pypa/gh-action-pypi-publish        │
└───────────────────────────────────────────────────────┘
```

Monitor progress at: `https://github.com/analogdata/analogdata-esp/actions`

---

## Part 4: After the release — update distribution packages

After GitHub Actions completes and the release is live:

**Homebrew** — update the formula SHA256 (see [homebrew-tap.md](homebrew-tap.md))

**APT** — upload the new `.deb` to Packagecloud (see [debian-apt.md](debian-apt.md))

---

## Deleting a bad tag (if you need to redo a release)

```bash
# Delete locally
git tag -d v0.2.0

# Delete on GitHub
git push origin --delete v0.2.0

# Re-tag after fixing the issue
git tag v0.2.0
git push origin v0.2.0
```

---

## Versioning convention

Follow semantic versioning (`MAJOR.MINOR.PATCH`):

| Change | Version bump | Example |
|---|---|---|
| New command, new feature | MINOR | 0.1.0 → 0.2.0 |
| Bug fix, small improvement | PATCH | 0.1.0 → 0.1.1 |
| Breaking change (renamed command etc) | MAJOR | 0.x.x → 1.0.0 |

Pre-release tags (e.g. `v0.2.0-beta.1`) are automatically marked as pre-release in GitHub.
