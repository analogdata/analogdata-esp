#!/usr/bin/env bash
# packaging/debian/build-deb.sh
#
# Builds a .deb package from a pre-built PyInstaller onedir binary.
# Run from the repo root AFTER pyinstaller analogdata-esp.spec has completed.
#
# Usage:
#   ./packaging/debian/build-deb.sh [version]
#   ./packaging/debian/build-deb.sh 0.2.0
#
# Output:
#   dist/analogdata-esp_<version>_amd64.deb
#
# Install the resulting .deb:
#   sudo dpkg -i dist/analogdata-esp_<version>_amd64.deb
#   analogdata-esp --help

set -euo pipefail
cd "$(dirname "$0")/../.."   # run from repo root regardless of where the script is called from

# ── Version ──────────────────────────────────────────────────────────────────
# Use the first argument, or read from pyproject.toml if not supplied
VERSION="${1:-$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)}"

# ── Paths ────────────────────────────────────────────────────────────────────
# With PyInstaller onedir mode, the output is a DIRECTORY not a single file:
#   dist/analogdata-esp/               ← the bundle directory
#   dist/analogdata-esp/analogdata-esp ← the actual binary
#   dist/analogdata-esp/_internal/     ← shared libraries and .pyc files
BUNDLE_DIR="dist/analogdata-esp"
BINARY="${BUNDLE_DIR}/analogdata-esp"
DEB_ROOT="dist/deb-build/analogdata-esp_${VERSION}_amd64"

echo "Building analogdata-esp_${VERSION}_amd64.deb ..."

# ── Sanity check ─────────────────────────────────────────────────────────────
if [[ ! -d "${BUNDLE_DIR}" ]]; then
    echo "ERROR: ${BUNDLE_DIR}/ not found."
    echo "       Run 'uv run pyinstaller analogdata-esp.spec --noconfirm' first."
    exit 1
fi

if [[ ! -f "${BINARY}" ]]; then
    echo "ERROR: binary not found at ${BINARY}"
    exit 1
fi

# ── Create .deb directory structure ──────────────────────────────────────────
# On the user's machine the layout will be:
#   /usr/lib/analogdata-esp/analogdata-esp   ← real binary
#   /usr/lib/analogdata-esp/_internal/       ← PyInstaller libs (must be beside binary)
#   /usr/local/bin/analogdata-esp            ← thin wrapper script → /usr/lib/...
rm -rf "${DEB_ROOT}"
mkdir -p "${DEB_ROOT}/DEBIAN"
mkdir -p "${DEB_ROOT}/usr/lib/analogdata-esp"
mkdir -p "${DEB_ROOT}/usr/local/bin"

# ── Copy the entire onedir bundle ─────────────────────────────────────────────
# The binary and _internal/ must stay in the same directory — PyInstaller
# looks for _internal/ relative to the binary's location at runtime.
cp    "${BINARY}"                        "${DEB_ROOT}/usr/lib/analogdata-esp/analogdata-esp"
cp -r "${BUNDLE_DIR}/_internal"          "${DEB_ROOT}/usr/lib/analogdata-esp/_internal"
chmod 0755 "${DEB_ROOT}/usr/lib/analogdata-esp/analogdata-esp"

# ── Create a wrapper script in /usr/local/bin ─────────────────────────────────
# Users run `analogdata-esp` — this wrapper execs the real binary in /usr/lib.
cat > "${DEB_ROOT}/usr/local/bin/analogdata-esp" << 'WRAPPER'
#!/bin/sh
exec /usr/lib/analogdata-esp/analogdata-esp "$@"
WRAPPER
chmod 0755 "${DEB_ROOT}/usr/local/bin/analogdata-esp"

# ── Write DEBIAN/control metadata file ───────────────────────────────────────
cat > "${DEB_ROOT}/DEBIAN/control" << EOF
Package: analogdata-esp
Version: ${VERSION}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: Rajath Kumar <hello@analogdata.io>
Homepage: https://github.com/analogdata/analogdata-esp
Description: Analog Data ESP-IDF CLI for embedded engineers
 ESP-IDF project scaffolding and AI agent for embedded engineers.
 Supports ESP32, ESP32-S2/S3, ESP32-C3/C6/H2/P4 targets.
 .
 Commands:
   analogdata-esp new <project>      Scaffold a new ESP-IDF project
   analogdata-esp agent "<question>" Ask the AI agent (Ollama or Gemini)
   analogdata-esp build              Build the current project
   analogdata-esp flash              Flash to connected device
   analogdata-esp doctor             Check ESP-IDF environment health
EOF

# ── Build the .deb ────────────────────────────────────────────────────────────
dpkg-deb --build "${DEB_ROOT}"

OUTPUT="dist/analogdata-esp_${VERSION}_amd64.deb"
mv "${DEB_ROOT}.deb" "${OUTPUT}"

echo ""
echo "✅  Built: ${OUTPUT}"
echo ""
echo "Install with:"
echo "  sudo dpkg -i ${OUTPUT}"
echo ""
echo "Or add to an APT repo and install with:"
echo "  sudo apt install analogdata-esp"
