#!/usr/bin/env bash
# Build standalone binary + platform package locally.
# Run from repo root.
#
# Usage:
#   ./scripts/build-local.sh          # auto-detect platform
#   ./scripts/build-local.sh deb      # Linux .deb only
#   ./scripts/build-local.sh brew     # macOS binary only

set -euo pipefail

PLATFORM="${1:-auto}"
if [[ "${PLATFORM}" == "auto" ]]; then
    case "$(uname -s)" in
        Darwin)  PLATFORM="brew" ;;
        Linux)   PLATFORM="deb"  ;;
        MINGW*|CYGWIN*|MSYS*) PLATFORM="win" ;;
        *) echo "Unknown platform. Pass 'deb', 'brew', or 'win'."; exit 1 ;;
    esac
fi

echo "▶ Building analogdata-esp for platform: ${PLATFORM}"

# ── 1. Install build deps ──────────────────────────────────
uv add --dev pyinstaller 2>/dev/null || pip install -q pyinstaller

# ── 2. Run PyInstaller ────────────────────────────────────
echo "▶ Running PyInstaller..."
uv run pyinstaller analogdata-esp.spec --noconfirm

echo "✅  Binary built: dist/analogdata-esp"

# ── 3. Platform package ───────────────────────────────────
case "${PLATFORM}" in
  deb)
    echo "▶ Building .deb package..."
    bash packaging/debian/build-deb.sh
    ;;
  brew)
    echo ""
    echo "✅  macOS binary ready at: dist/analogdata-esp"
    echo ""
    echo "To test locally:"
    echo "  sudo cp dist/analogdata-esp /usr/local/bin/"
    echo "  analogdata-esp --help"
    echo ""
    echo "To update the Homebrew formula after uploading to GitHub Releases:"
    echo "  shasum -a 256 dist/analogdata-esp"
    echo "  # → paste SHA256 into packaging/homebrew/analogdata-esp.rb"
    ;;
  win)
    echo "▶ Building NSIS installer..."
    VERSION="$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)"
    echo "!define VERSION \"${VERSION}\"" > packaging/windows/version.nsh
    makensis /V2 packaging/windows/installer.nsi
    mv packaging/windows/analogdata-esp-setup.exe "dist/analogdata-esp-${VERSION}-setup.exe"
    echo "✅  Installer: dist/analogdata-esp-${VERSION}-setup.exe"
    ;;
esac
