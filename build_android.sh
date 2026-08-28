#!/usr/bin/env bash
#
# Builds the Swellfire Android package, ready to upload to Google Play.
#
# What it does:
#   1. Verifies the Play-critical target SDK and Android toolchain settings.
#   2. Activates the venv and makes sure buildozer and Cython are installed.
#   3. Checks that the Android build tools are present (installed by setup_venv.sh).
#   4. Creates a release upload key the first time, and exports its certificate.
#   5. Builds the signed release files in ./bin (an .aab for Google Play and an
#      .apk you can install on a device for testing).
#   6. Prints the files and their package id, target SDK and architectures.
#
# Options:
#   ./build_android.sh             build the release .aab and .apk
#   ./build_android.sh --debug     build a quick unsigned debug .apk only
#   ./build_android.sh --skip-deps do not check the system build tools
#   ./build_android.sh --check     validate config only; do not build or sign
#
# The first build downloads the Android SDK and NDK (a few GB) and can take
# 30 to 60 minutes. It must run on Linux.
#
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(pwd)"

MODE="release"
SKIP_DEPS=0
CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --debug)     MODE="debug" ;;
        --skip-deps) SKIP_DEPS=1 ;;
        --check)     CHECK_ONLY=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# Fail before downloads or signing if a Play-critical setting regresses. The
# check-only path deliberately stops here and never creates a venv or keystore.
python3 tools/check_android_config.py
if [[ "$CHECK_ONLY" -eq 1 ]]; then
    exit 0
fi

VENV_DIR="venv"
KEYSTORE_FILE="$PROJECT_DIR/swellfire-upload.keystore"
KEYSTORE_ALIAS="swellfire-upload"
ENV_FILE="$PROJECT_DIR/.env"
EXPECTED_UPLOAD_CERT_SHA256="564b9f2769f6bd80eda784cb29886cc28f0375531d653718e4c3e52f7c889b96"

# Make sure the venv and buildozer are ready.
if [[ ! -d "$VENV_DIR" ]]; then
    echo "venv missing, creating it with setup_venv.sh"
    ./setup_venv.sh
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
# Keep a compatible shared environment stable while allowing p4a's host Python
# to download its own build prerequisites later in the build.
python -m pip install 'buildozer>=1.5,<2' 'Cython>=0.29.34,<3.2'

# Check the Android build tools. setup_venv.sh installs them.
if [[ "$SKIP_DEPS" -eq 0 ]]; then
    missing=""
    command -v javac      >/dev/null 2>&1 || missing="$missing openjdk-17-jdk"
    command -v autoconf   >/dev/null 2>&1 || missing="$missing autoconf"
    command -v automake   >/dev/null 2>&1 || missing="$missing automake"
    command -v libtoolize >/dev/null 2>&1 || missing="$missing libtool"
    command -v cmake      >/dev/null 2>&1 || missing="$missing cmake"
    if [[ -n "$missing" ]]; then
        echo "Android build tools are missing:$missing" >&2
        echo "Run ./setup_venv.sh first, then run this script again." >&2
        exit 1
    fi
fi

# A quick debug build needs no signing.
if [[ "$MODE" == "debug" ]]; then
    echo "Building a debug apk"
    buildozer android debug
    echo "Done. Files in ./bin:"; ls -1 bin/ 2>/dev/null || true
    exit 0
fi

# Swellfire already has a production upload identity. Never create a new key
# automatically: doing so produces a valid-looking build that Google Play and
# existing direct installs will reject.
if [[ ! -f "$ENV_FILE" || ! -f "$KEYSTORE_FILE" ]]; then
    echo "Swellfire production signing files are missing." >&2
    echo "Restore .env and swellfire-upload.keystore from the secure backup." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$ENV_FILE"
: "${KEYSTORE_PASSWORD:?KEYSTORE_PASSWORD is missing from .env}"
: "${KEYSTORE_ALIAS:?KEYSTORE_ALIAS is missing from .env}"

ACTUAL_UPLOAD_CERT_SHA256="$(
    keytool -exportcert \
        -keystore "$KEYSTORE_FILE" \
        -alias "$KEYSTORE_ALIAS" \
        -storepass "$KEYSTORE_PASSWORD" 2>/dev/null \
        | sha256sum | awk '{print $1}'
)"
if [[ "$ACTUAL_UPLOAD_CERT_SHA256" != "$EXPECTED_UPLOAD_CERT_SHA256" ]]; then
    echo "Refusing to build with an unrecognized Android signing key." >&2
    echo "Expected certificate SHA-256: $EXPECTED_UPLOAD_CERT_SHA256" >&2
    echo "Actual certificate SHA-256:   $ACTUAL_UPLOAD_CERT_SHA256" >&2
    exit 1
fi
if [[ -f "$PROJECT_DIR/upload_certificate.pem" ]]; then
    PEM_CERT_SHA256="$(openssl x509 -in "$PROJECT_DIR/upload_certificate.pem" \
        -outform DER 2>/dev/null | sha256sum | awk '{print $1}')"
    if [[ "$PEM_CERT_SHA256" != "$EXPECTED_UPLOAD_CERT_SHA256" ]]; then
        echo "upload_certificate.pem does not match the production key." >&2
        exit 1
    fi
fi
echo "Verified Swellfire production upload certificate: $EXPECTED_UPLOAD_CERT_SHA256"

# Pass the keystore to python-for-android. The key password is the same as the
# store password because the keystore is in PKCS12 format.
export P4A_RELEASE_KEYSTORE="$KEYSTORE_FILE"
export P4A_RELEASE_KEYSTORE_PASSWD="$KEYSTORE_PASSWORD"
export P4A_RELEASE_KEYALIAS="$KEYSTORE_ALIAS"
export P4A_RELEASE_KEYALIAS_PASSWD="$KEYSTORE_PASSWORD"
# Keep p4a's generated Python 3.14 venv on its bundled, known-good pip. This is
# exported only after the host build dependencies above have been checked, so
# it does not constrain the reusable developer venv.
export PIP_CONSTRAINT="$PROJECT_DIR/android/pip-constraints.txt"


# python-for-android builds one file type per run, so build the aab and the apk
# in two passes. Always leave buildozer.spec set back to aab when done.
set_artifact() {
    sed -i "s/^android.release_artifact = .*/android.release_artifact = $1/" buildozer.spec
}
trap 'set_artifact aab' EXIT

echo "Building the release aab for Google Play"
set_artifact aab
buildozer android release

echo "Building the release apk for testing on a device"
set_artifact apk
buildozer android release

# Report the files.
echo ""
echo "Build finished. Files in ./bin:"
ls -1 bin/ 2>/dev/null || true

# Print package details from the apk using aapt from the downloaded SDK.
AAPT="$(find "$HOME/.buildozer" -type f -name aapt 2>/dev/null | sort | tail -1 || true)"
APK="$(ls -1 bin/*.apk 2>/dev/null | head -1 || true)"
if [[ -n "$AAPT" && -n "$APK" ]]; then
    echo ""
    echo "Details of $APK:"
    "$AAPT" dump badging "$APK" | grep -E "package:|sdkVersion:|targetSdkVersion:|native-code:" || true
fi

echo ""
echo "Next steps:"
echo "  Upload the .aab in ./bin to Google Play as a new release."
echo "  If Play rejects the version code, raise android.numeric_version in"
echo "  buildozer.spec and build again."
echo "  For signing or lost key questions, see SIGNING.md."
