# Homebrew Tap — How it Works and How to Set It Up

---

## How Homebrew finds your package

When a user runs:
```bash
brew tap analogdata/tap
brew install analogdata-esp
```

Here is exactly what Homebrew does:

```
brew tap analogdata/tap
        │
        ▼
Homebrew clones: https://github.com/analogdata/homebrew-tap
                 into: $(brew --prefix)/Library/Taps/analogdata/homebrew-tap/

brew install analogdata-esp
        │
        ▼
Looks for file: homebrew-tap/Formula/analogdata-esp.rb
        │
        ▼
Reads the formula:
  - url  → downloads the binary from GitHub Releases
  - sha256 → verifies the download
  - def install → copies binary to bin/
        │
        ▼
Binary available at: /usr/local/bin/analogdata-esp (Intel)
                  or /opt/homebrew/bin/analogdata-esp (Apple Silicon)
```

The key insight: **your tap repo IS the package registry**. It's just a GitHub repo with a formula file. Homebrew fetches it directly.

---

## Part 1: Create the tap repository (one-time setup)

### 1. Create the GitHub repository

Name it exactly: **`homebrew-tap`** under your `analogdata` org/account.
The naming convention `homebrew-<tapname>` is how Homebrew finds it.

```
GitHub repo: analogdata/homebrew-tap
User command: brew tap analogdata/tap    ← "tap" maps to "homebrew-tap"
```

Create it at: https://github.com/new
- Name: `homebrew-tap`
- Public repository (required)
- Initialize with a README

### 2. Create the Formula directory

```bash
git clone https://github.com/analogdata/homebrew-tap.git
cd homebrew-tap
mkdir Formula
```

### 3. Copy in the formula template

```bash
cp /Users/rajathkumar/analogdata-esp/packaging/homebrew/analogdata-esp.rb Formula/analogdata-esp.rb
```

### 4. Fill in the SHA256 for your first release

After GitHub Actions creates the v0.1.0 release:

```bash
# Download the macOS binary from the release
curl -Lo analogdata-esp-arm64 \
  https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp-macos-arm64

# Get the SHA256
shasum -a 256 analogdata-esp-arm64
# → e.g. a3f8c2d1...  analogdata-esp-arm64
```

Edit `Formula/analogdata-esp.rb` and replace the placeholder:
```ruby
url "https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp-macos-arm64"
sha256 "a3f8c2d1..."     # ← paste your actual SHA256 here
```

### 5. Push the formula

```bash
git add Formula/analogdata-esp.rb
git commit -m "Add analogdata-esp v0.1.0 formula"
git push
```

### 6. Test it

```bash
# Install from your tap
brew tap analogdata/tap
brew install analogdata-esp

# Verify
analogdata-esp --help
analogdata-esp doctor

# Uninstall when done testing
brew uninstall analogdata-esp
brew untap analogdata/tap
```

---

## Part 2: Updating the formula after a new release

Every time you release a new version, you must update the formula. This is a ~2 minute process.

### Automated approach (recommended)

Add this to your release checklist or create a script:

```bash
#!/usr/bin/env bash
# scripts/update-homebrew-formula.sh
# Run after GitHub Actions has completed the release.

set -euo pipefail

VERSION="${1:?Usage: $0 <version>   e.g. $0 0.2.0}"
BINARY_URL="https://github.com/analogdata/analogdata-esp/releases/download/v${VERSION}/analogdata-esp-macos-arm64"
TAP_DIR="${HOME}/src/homebrew-tap"   # ← path where you cloned homebrew-tap

echo "▶ Downloading macOS binary for v${VERSION}..."
curl -Lo /tmp/analogdata-esp-arm64 "${BINARY_URL}"

SHA=$(shasum -a 256 /tmp/analogdata-esp-arm64 | awk '{print $1}')
echo "▶ SHA256: ${SHA}"

FORMULA="${TAP_DIR}/Formula/analogdata-esp.rb"

# Update url
sed -i '' "s|releases/download/v[0-9.]*/analogdata-esp-macos-arm64|releases/download/v${VERSION}/analogdata-esp-macos-arm64|" "${FORMULA}"

# Update sha256
sed -i '' "s/sha256 \"[a-f0-9]*\"/sha256 \"${SHA}\"/" "${FORMULA}"

# Update version
sed -i '' "s/version \"[0-9.]*\"/version \"${VERSION}\"/" "${FORMULA}"

echo "▶ Committing..."
cd "${TAP_DIR}"
git add Formula/analogdata-esp.rb
git commit -m "Update analogdata-esp to v${VERSION}"
git push

echo "✅  Homebrew formula updated. Users can now run: brew upgrade analogdata-esp"
rm /tmp/analogdata-esp-arm64
```

Usage:
```bash
./scripts/update-homebrew-formula.sh 0.2.0
```

### Manual approach

1. Go to the GitHub Release page, right-click the `analogdata-esp-macos-arm64` asset → **Copy link address**
2. Download and hash it:
   ```bash
   curl -Lo /tmp/ae-arm64 <paste-url>
   shasum -a 256 /tmp/ae-arm64
   ```
3. Edit `Formula/analogdata-esp.rb` — update `url`, `sha256`, and `version`
4. Commit and push to `homebrew-tap`

---

## Part 3: Supporting Intel Macs (x86_64)

The GitHub Actions workflow builds on `macos-14` (Apple Silicon). To also support Intel:

Add a second matrix entry in `.github/workflows/release.yml`:
```yaml
- os: macos-13          # Intel runner
  artifact_name: analogdata-esp-macos-x86_64
  asset_name:    analogdata-esp-macos-x86_64
```

Then update the formula:
```ruby
on_arm do
  url "https://github.com/analogdata/analogdata-esp/releases/download/v0.2.0/analogdata-esp-macos-arm64"
  sha256 "ARM64_SHA_HERE"
end

on_intel do
  url "https://github.com/analogdata/analogdata-esp/releases/download/v0.2.0/analogdata-esp-macos-x86_64"
  sha256 "X86_SHA_HERE"
end
```

Homebrew automatically picks the correct one for each Mac.

---

## The formula file explained

```ruby
class AnalogdataEsp < Formula
  desc "ESP-IDF project scaffolding and AI agent"   # brew search description
  homepage "https://github.com/analogdata/analogdata-esp"

  url "https://github.com/.../analogdata-esp-macos-arm64"
  sha256 "abc123..."     # Homebrew verifies the download against this
  version "0.1.0"        # shown in brew info
  license "MIT"

  bottle :unneeded       # tells Homebrew: no bottle compilation needed (pre-built binary)

  def install
    # Installs the downloaded file as "analogdata-esp" in Homebrew's bin
    bin.install "analogdata-esp-macos-arm64" => "analogdata-esp"
  end

  test do
    # Homebrew runs this to verify the install worked
    assert_match "Analog Data", shell_output("#{bin}/analogdata-esp --help")
  end
end
```

---

## User experience after setup

```bash
# First time
brew tap analogdata/tap
brew install analogdata-esp
analogdata-esp --help     # works immediately

# Future updates
brew upgrade analogdata-esp

# Check version
brew info analogdata-esp
```

Homebrew caches the tap locally and `brew update` refreshes it from GitHub. When you push a new formula, users get it on their next `brew upgrade analogdata-esp`.
