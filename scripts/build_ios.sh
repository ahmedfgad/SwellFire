#!/usr/bin/env bash
#
# Builds the Swellfire iOS app with kivy-ios.
#
# iOS apps can only be built on a Mac with Xcode. This script stops if it is run
# anywhere else. It cannot run on Linux.
#
# What it does on a Mac:
#   1. Checks for Xcode command line tools and Homebrew.
#   2. Installs the packages kivy-ios needs (autoconf, automake, libtool, pkg-config).
#   3. Creates a Python venv and installs kivy-ios and Cython.
#   4. Builds the iOS toolchain (python3 and kivy).
#   5. Creates an Xcode project from this app.
#   6. Prints the steps left to do in Xcode.
#
# Run it on a Mac with:
#   ./scripts/build_ios.sh
#
set -euo pipefail
SCRIPT_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

if [[ "${1:-}" == "--check" ]]; then
    python3 tools/check_ios_config.py
    exit 0
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--check]" >&2
    exit 2
fi

# shellcheck disable=SC1091
source ios/app.env
APP_TITLE="$IOS_APP_NAME"
IOS_VENV=".ios-venv"

# Stop if this is not a Mac.
if [[ "$(uname)" != "Darwin" ]]; then
    echo "iOS builds need macOS and Xcode." >&2
    echo "This machine is $(uname), so the build cannot run here." >&2
    echo "Copy the project to a Mac and run this script there. You also need:" >&2
    echo "  - An Apple Developer account to sign and publish the app." >&2
    echo "  - Xcode from the Mac App Store, with its command line tools." >&2
    exit 1
fi

# Check Xcode command line tools.
if ! xcode-select -p >/dev/null 2>&1; then
    echo "Installing Xcode command line tools (a window may open)."
    xcode-select --install || true
    echo "Run this script again after the install finishes." >&2
    exit 1
fi

# Check Homebrew.
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required. Install it from https://brew.sh and run this again." >&2
    exit 1
fi

SDK_VERSION=$(xcrun --sdk iphoneos --show-sdk-version)
SDK_MAJOR=${SDK_VERSION%%.*}
if [[ "$SDK_MAJOR" -lt "$IOS_MIN_XCODE_MAJOR" ]]; then
    echo "Xcode with the iOS $IOS_MIN_XCODE_MAJOR SDK or newer is required." >&2
    echo "Selected toolchain: $(xcodebuild -version | head -1), iPhoneOS SDK $SDK_VERSION" >&2
    exit 1
fi

echo "Installing build packages with Homebrew"
brew install autoconf automake libtool pkg-config libjpeg

# Create the venv and install kivy-ios.
if [[ ! -d "$IOS_VENV" ]]; then
    echo "Creating iOS build venv ($IOS_VENV)"
    python3 -m venv "$IOS_VENV"
fi
# shellcheck disable=SC1091
source "$IOS_VENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements/ios.txt

# Build the toolchain. This is the long step.
echo "Building the iOS toolchain (python3 and kivy)"
toolchain build python3 kivy
toolchain pip install certifi

# Stage only runtime files so repository metadata, docs, and build credentials can never enter the app bundle.
STAGE_DIR="ios_app"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR/assets" "$STAGE_DIR/swellfire"
rsync -a main.py "$STAGE_DIR/"
rsync -a --include='*/' --include='*.py' --exclude='*' swellfire/ "$STAGE_DIR/swellfire/"
rsync -a --exclude="raw/" assets/ "$STAGE_DIR/assets/"

# Create the Xcode project.
echo "Creating the Xcode project for $APP_TITLE"
PROJ_DIR="${APP_TITLE}-ios"
rm -rf "$PROJ_DIR"
toolchain create "$APP_TITLE" "$STAGE_DIR"
test -d "$PROJ_DIR"

# Replace the kivy-ios template's Kivy-logo icon and launch screen with the
# Swellfire artwork. Without this, the installed app shows the Kivy logo on the
# home screen and again as the splash screen.
echo "Applying the Swellfire icon and presplash"
"$PROJECT_DIR/tools/ios_apply_assets.sh" \
    "$PROJ_DIR" icon.png presplash.png
python tools/ios_configure_project.py "$PROJ_DIR"
XCODEPROJ=$(find "$PROJ_DIR" -maxdepth 1 -name "*.xcodeproj" | head -1)

echo ""
echo "Xcode project created: $PROJ_DIR"
echo ""
echo "Next steps in Xcode:"
echo "  1. open $XCODEPROJ"
echo "  2. In Signing and Capabilities select your Apple Developer team."
echo "     Bundle ID: $IOS_BUNDLE_ID"
echo "  3. Choose Any iOS Device and run Product > Archive."
echo "  4. Validate in Organizer, then test through TestFlight before submission."
echo "  5. Follow docs/release/app-store.md for the listing and review checklist."
echo ""
echo "Note: iOS signing uses Apple certificates and is separate from the Android"
echo "keystore."
