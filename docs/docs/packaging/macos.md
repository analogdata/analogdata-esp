# macOS Installation

---

## Homebrew (Recommended)

Homebrew is the easiest way to install and keep `analogdata-esp` up to date on macOS.

```bash
brew tap analogdata/tap
brew install analogdata-esp
```

### Updating

```bash
brew update
brew upgrade analogdata-esp
```

### Uninstalling

```bash
brew uninstall analogdata-esp
```

---

## Direct Binary Download

1. Go to the [GitHub Releases page](https://github.com/analogdata/analogdata-esp/releases/latest)
2. Download the macOS binary: `analogdata-esp-macos`
3. Make it executable and move it into your PATH:

```bash
chmod +x analogdata-esp-macos
sudo mv analogdata-esp-macos /usr/local/bin/analogdata-esp
```

4. Verify:

```bash
analogdata-esp --help
```

!!! note "macOS Gatekeeper"
    If macOS blocks the binary with "cannot be opened because it is from an unidentified developer", run:

    ```bash
    xattr -dr com.apple.quarantine /usr/local/bin/analogdata-esp
    ```

---

## pip / pipx

If you have Python 3.10+ installed:

```bash
# pipx (recommended — runs in an isolated environment)
pipx install analogdata-esp

# pip (global install)
pip install analogdata-esp
```

Install `pipx` if needed:

```bash
brew install pipx
pipx ensurepath
```

### Uninstalling

```bash
pipx uninstall analogdata-esp
# or
pip uninstall analogdata-esp
```

---

## From Source

```bash
git clone https://github.com/analogdata/analogdata-esp.git
cd analogdata-esp
uv sync
uv run analogdata-esp --help
```

See [Local Installation](../getting-started/local-install.md) for the full developer setup guide.

---

## Maintainer: Setting Up the Homebrew Tap

This section is for project maintainers who manage the `analogdata/homebrew-tap` repository.

### 1. Create the tap repository

Create a public GitHub repository named `homebrew-tap` under the `analogdata` organisation:

```
https://github.com/analogdata/homebrew-tap
```

### 2. Create the formula file

In the tap repository, create `Formula/analogdata-esp.rb`:

```ruby
class AnaldataEsp < Formula
  desc "ESP-IDF CLI for embedded engineers — by Analog Data"
  homepage "https://docs.analogdata.io/esp-cli"
  url "https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp-macos"
  sha256 "<sha256 of the binary>"
  version "0.1.0"

  def install
    bin.install "analogdata-esp-macos" => "analogdata-esp"
  end

  test do
    system "#{bin}/analogdata-esp", "--version"
  end
end
```

### 3. Update on each release

The GitHub Actions release pipeline automatically opens a PR against the tap repository to update the URL and SHA256 hash when a new version tag is pushed.

### 4. Verify the tap works

```bash
brew tap analogdata/tap
brew install analogdata-esp
analogdata-esp --version
```
