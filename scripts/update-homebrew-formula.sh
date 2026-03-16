#!/usr/bin/env bash
# Update the Homebrew formula after a GitHub release.
# Run this AFTER GitHub Actions has finished building the release.
#
# Usage:
#   ./scripts/update-homebrew-formula.sh <version> <path-to-homebrew-tap-repo>
#
# Example:
#   ./scripts/update-homebrew-formula.sh 0.2.0 ~/src/homebrew-tap

set -euo pipefail

VERSION="${1:?Usage: $0 <version> <tap-repo-path>  e.g.: $0 0.2.0 ~/src/homebrew-tap}"
TAP_DIR="${2:?Usage: $0 <version> <tap-repo-path>  e.g.: $0 0.2.0 ~/src/homebrew-tap}"
FORMULA="${TAP_DIR}/Formula/analogdata-esp.rb"
REPO="analogdata/analogdata-esp"
BASE_URL="https://github.com/${REPO}/releases/download/v${VERSION}"

echo "▶ Updating Homebrew formula to v${VERSION}"

# ── Download binaries and hash them ──────────────────────────────────────────
echo "▶ Downloading macOS arm64 binary..."
curl -fsSLo /tmp/ae-macos-arm64 "${BASE_URL}/analogdata-esp-macos-arm64"
SHA_ARM64=$(shasum -a 256 /tmp/ae-macos-arm64 | awk '{print $1}')
echo "  arm64 SHA256: ${SHA_ARM64}"

# Uncomment when you add an Intel build to the release workflow:
# echo "▶ Downloading macOS x86_64 binary..."
# curl -fsSLo /tmp/ae-macos-x86_64 "${BASE_URL}/analogdata-esp-macos-x86_64"
# SHA_X86=$(shasum -a 256 /tmp/ae-macos-x86_64 | awk '{print $1}')
# echo "  x86_64 SHA256: ${SHA_X86}"

# ── Patch the formula ────────────────────────────────────────────────────────
echo "▶ Patching formula..."

# Update download URL
sed -i '' \
  "s|releases/download/v[0-9.][0-9.]*/analogdata-esp-macos-arm64|releases/download/v${VERSION}/analogdata-esp-macos-arm64|g" \
  "${FORMULA}"

# Update sha256 (first occurrence — arm64)
sed -i '' \
  "s/sha256 \"[a-f0-9]\{64\}\"/sha256 \"${SHA_ARM64}\"/" \
  "${FORMULA}"

# Update version string
sed -i '' \
  "s/version \"[0-9.]*\"/version \"${VERSION}\"/" \
  "${FORMULA}"

echo "▶ Formula after update:"
grep -E "url|sha256|version" "${FORMULA}"

# ── Commit and push ──────────────────────────────────────────────────────────
echo "▶ Committing to homebrew-tap..."
cd "${TAP_DIR}"
git add Formula/analogdata-esp.rb
git commit -m "analogdata-esp ${VERSION}"
git push

echo ""
echo "✅  Done! Users can now run:"
echo "     brew upgrade analogdata-esp"
echo ""

# Cleanup
rm -f /tmp/ae-macos-arm64 /tmp/ae-macos-x86_64
