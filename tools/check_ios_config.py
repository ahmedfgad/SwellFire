#!/usr/bin/env python3
"""Validate App Store-critical iOS settings without macOS, building, or signing."""

from __future__ import annotations

import plistlib
import re
from pathlib import Path

from ios_configure_project import load_config, validate_config


ROOT = Path(__file__).resolve().parents[1]


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"iOS configuration check failed: {message}")


def buildozer_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}\s*=\s*(.+?)\s*$", text, re.MULTILINE)
    expect(match is not None, f"buildozer.spec is missing {key}")
    return match.group(1)


def main() -> None:
    config = load_config()
    validate_config(config)

    android = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    android_id = f"{buildozer_value(android, 'package.domain')}.{buildozer_value(android, 'package.name')}"
    expect(config["IOS_BUNDLE_ID"] == android_id, "iOS and Android application IDs differ")
    expect(config["IOS_MARKETING_VERSION"] == buildozer_value(android, "version"), "iOS and Android versions differ")

    with (ROOT / "ios" / "PrivacyInfo.xcprivacy").open("rb") as stream:
        privacy = plistlib.load(stream)
    expect(privacy.get("NSPrivacyTracking") is False, "privacy manifest must disable tracking")
    expect(bool(privacy.get("NSPrivacyAccessedAPITypes")), "privacy manifest has no required-reason API entries")

    workflow = "\n".join(
        (ROOT / ".github" / "workflows" / path).read_text(encoding="utf-8")
        for path in ("ios-build.yml", "ios-app-store.yml")
    )
    for required in (
        "runs-on: macos-26",
        "requirements-ios.txt",
        "toolchain pip install certifi",
        "tools/ios_configure_project.py",
        "Archive iOS for App Store",
        "xcodebuild archive",
        "-exportArchive",
        "APPLE_DISTRIBUTION_CERTIFICATE_BASE64",
        "APPLE_PROVISIONING_PROFILE_BASE64",
    ):
        expect(required in workflow, f"iOS workflow is missing {required!r}")

    asset_script = "\n".join(
        (ROOT / "tools" / path).read_text(encoding="utf-8")
        for path in ("ios_apply_assets.sh", "ios_generate_icons.py")
    )
    for required in ("ios-marketing", "1024x1024", "83.5x83.5", 'convert("RGB")'):
        expect(required in asset_script, f"App Store icon generator is missing {required!r}")

    for path in (
        "APP_STORE_RELEASE.md",
        "PRIVACY.md",
        "SUPPORT.md",
        "ios/app-store-metadata.md",
        "tools/make_app_store_screenshots.py",
    ):
        expect((ROOT / path).is_file(), f"missing {path}")

    print("iOS App Store configuration OK")
    print(f"  bundle: {config['IOS_BUNDLE_ID']}")
    print(f"  version: {config['IOS_MARKETING_VERSION']} ({config['IOS_BUILD_NUMBER']})")
    print(f"  minimum iOS: {config['IOS_DEPLOYMENT_TARGET']}")
    print(f"  minimum Xcode: {config['IOS_MIN_XCODE_MAJOR']}")
    print("  devices: iPhone + iPad; Apple-silicon Mac compatibility may be enabled in App Store Connect")


if __name__ == "__main__":
    main()
