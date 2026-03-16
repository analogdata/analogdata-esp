#!/usr/bin/env bash
# packaging/build_release.sh
# Build release tarballs for GitHub releases.
#
# Usage:
#   ./packaging/build_release.sh [version]
#   ./packaging/build_release.sh v0.2.0
#
# Output (in dist/):
#   analogdata-esp-macos-arm64-v0.x.x.tar.gz
#   analogdata-esp-macos-arm64-v0.x.x.tar.gz.sha256

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-v0.1.0}"
ARCH="$(uname -m)"   # arm64 or x86_64
PLATFORM="macos-${ARCH}"
TARBALL_NAME="analogdata-esp-${PLATFORM}-${VERSION}.tar.gz"

echo "🔨 Building analogdata-esp ${VERSION} for ${PLATFORM}..."

# Activate venv
source .venv/bin/activate

# Clean previous build
rm -rf dist/analogdata-esp build/

# Build onedir binary
pyinstaller analogdata-esp.spec --noconfirm

echo "📦 Creating tarball: dist/${TARBALL_NAME}"

# Package: tar the directory, keep internal path as analogdata-esp/
tar -czf "dist/${TARBALL_NAME}" -C dist analogdata-esp

# SHA256
SHA=$(shasum -a 256 "dist/${TARBALL_NAME}" | awk '{print $1}')
echo "${SHA}  ${TARBALL_NAME}" > "dist/${TARBALL_NAME}.sha256"

echo ""
echo "✅ Done!"
echo ""
echo "   Tarball : dist/${TARBALL_NAME}"
echo "   SHA256  : ${SHA}"
echo ""
echo "Next steps:"
echo "  1. Create a GitHub release: gh release create ${VERSION} dist/${TARBALL_NAME}"
echo "  2. Update homebrew-analogdata-esp/Formula/analogdata-esp.rb:"
echo "       url    → https://github.com/<user>/analogdata-esp/releases/download/${VERSION}/${TARBALL_NAME}"
echo "       sha256 → ${SHA}"
echo "  3. Push the formula: cd ~/homebrew-analogdata-esp && git add -A && git commit -m 'Release ${VERSION}' && git push"
