# Homebrew formula for analogdata-esp
#
# This file lives in a separate tap repository:
#   https://github.com/analogdata/homebrew-tap
#
# Users install with:
#   brew tap analogdata/tap
#   brew install analogdata-esp
#
# To update after a new release:
#   1. Update `url` to the new GitHub release asset URL
#   2. Update `sha256` — run: shasum -a 256 <downloaded-binary>
#   3. Commit + push to the homebrew-tap repo

class AnalogdataEsp < Formula
  desc "ESP-IDF project scaffolding and AI agent for embedded engineers"
  homepage "https://github.com/analogdata/analogdata-esp"

  # ── Release binary (no Python required on user's machine) ──────────────
  # Update these two lines on every release:
  url "https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp-macos-arm64"
  sha256 "REPLACE_WITH_SHA256_FROM_RELEASE"        # shasum -a 256 analogdata-esp-macos-arm64

  version "0.1.0"
  license "MIT"

  # Intel Mac override
  on_intel do
    url "https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp-macos-x86_64"
    sha256 "REPLACE_WITH_SHA256_INTEL"
  end

  def install
    bin.install "analogdata-esp-macos-arm64" => "analogdata-esp"
  rescue
    bin.install "analogdata-esp-macos-x86_64" => "analogdata-esp"
  end

  test do
    assert_match "Analog Data", shell_output("#{bin}/analogdata-esp --help")
  end
end
