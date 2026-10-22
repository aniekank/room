#!/bin/bash
# Builds dist/Room.app and dist/Room.dmg (drag-to-Applications).
#
#   packaging/build.sh                      unsigned build (friends see a Gatekeeper warning)
#   ROOM_SIGN_ID="Developer ID Application: Your Name (TEAMID)" \
#   ROOM_NOTARY_PROFILE=room packaging/build.sh   signed + notarized, opens with no warning
#
# The notary profile is made once with:
#   xcrun notarytool store-credentials room --apple-id you@example.com --team-id TEAMID
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# python.org's universal2 Python, so one build runs on Intel and Apple Silicon Macs.
PY="${ROOM_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}"
export ROOM_VERSION="${ROOM_VERSION:-$(date +%Y.%m.%d)}"

if [ ! -d .build-venv ]; then
  "$PY" -m venv .build-venv
  .build-venv/bin/pip install -q --upgrade pip
fi
.build-venv/bin/pip install -q --upgrade pyinstaller rumps pillow -r requirements.txt

.build-venv/bin/python packaging/make_icons.py build/icons
rm -rf build/Room dist/Room dist/Room.app dist/Room.dmg
.build-venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/Room.spec
rm -rf dist/Room  # the loose folder; the .app is the product

if [ -n "$ROOM_SIGN_ID" ]; then
  codesign --force --deep --options runtime --timestamp --entitlements packaging/entitlements.plist \
    --sign "$ROOM_SIGN_ID" dist/Room.app
fi

STAGE="build/dmg"
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R dist/Room.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname Room -srcfolder "$STAGE" -ov -format UDZO dist/Room.dmg

if [ -n "$ROOM_SIGN_ID" ]; then
  codesign --sign "$ROOM_SIGN_ID" --timestamp dist/Room.dmg
  if [ -n "$ROOM_NOTARY_PROFILE" ]; then
    xcrun notarytool submit dist/Room.dmg --keychain-profile "$ROOM_NOTARY_PROFILE" --wait
    xcrun stapler staple dist/Room.dmg
  fi
fi
echo "Built dist/Room.app and dist/Room.dmg ($ROOM_VERSION)"
