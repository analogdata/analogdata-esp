#!/usr/bin/env bash
# Build a .deb package from a pre-built PyInstaller binary.
# Run from the repo root after `pyinstaller analogdata-esp.spec`.
#
# Usage:
#   ./packaging/debian/build-deb.sh [version]
#
# Example:
#   ./packaging/debian/build-deb.sh 0.1.0

set -euo pipefail

BINARY="dist/analogdata-esp"
VERSION="${1:-$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)}"
DEB_ROOT="dist/deb-build/analogdata-esp_${VERSION}_amd64"

echo "Building analogdata-esp_${VERSION}_amd64.deb ..."

# ── Verify binary exists ──────────────────────────────────
if [[ ! -f "${BINARY}" ]]; then
    echo "ERROR: ${BINARY} not found. Run 'pyinstaller analogdata-esp.spec' first."
    exit 1
fi

# ── Create deb directory structure ───────────────────────
rm -rf "${DEB_ROOT}"
mkdir -p "${DEB_ROOT}/DEBIAN"
mkdir -p "${DEB_ROOT}/usr/local/bin"

# ── Copy binary ───────────────────────────────────────────
cp "${BINARY}" "${DEB_ROOT}/usr/local/bin/analogdata-esp"
chmod 0755 "${DEB_ROOT}/usr/local/bin/analogdata-esp"

# ── Write control file ────────────────────────────────────
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
EOF

# ── Build .deb ────────────────────────────────────────────
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
