#!/usr/bin/env python3
"""Validate Play-critical Android settings without building or signing."""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path


MIN_TARGET_API = 36
MIN_VERSION_CODE = 10001
PINNED_NDK = "28c"
PINNED_P4A_BRANCH = "develop"
PINNED_P4A_COMMIT = "58d21141f17c889bf8585f5665921d72028f8831"


def main() -> int:
    project_dir = Path(__file__).resolve().parent.parent
    spec_path = project_dir / "buildozer.spec"
    parser = configparser.RawConfigParser()

    if not parser.read(spec_path, encoding="utf-8"):
        print(f"ERROR: could not read {spec_path}", file=sys.stderr)
        return 1

    errors: list[str] = []

    def value(name: str) -> str:
        try:
            return parser.get("app", name).strip()
        except (configparser.Error, KeyError):
            errors.append(f"missing [app] {name}")
            return ""

    target_text = value("android.api")
    try:
        target_api = int(target_text)
    except ValueError:
        errors.append(f"android.api must be an integer, got {target_text!r}")
        target_api = 0
    if target_api < MIN_TARGET_API:
        errors.append(
            f"android.api must be at least {MIN_TARGET_API} for Google Play; "
            f"got {target_api}"
        )

    min_api_text = value("android.minapi")
    ndk_api_text = value("android.ndk_api")
    if not min_api_text.isdigit():
        errors.append(f"android.minapi must be an integer, got {min_api_text!r}")
    if not ndk_api_text.isdigit():
        errors.append(f"android.ndk_api must be an integer, got {ndk_api_text!r}")
    if (
        min_api_text.isdigit()
        and ndk_api_text.isdigit()
        and min_api_text != ndk_api_text
    ):
        errors.append(
            "android.ndk_api must match android.minapi "
            f"({ndk_api_text} != {min_api_text})"
        )

    ndk = value("android.ndk")
    if ndk != PINNED_NDK:
        errors.append(f"android.ndk must be {PINNED_NDK}, got {ndk!r}")

    p4a_branch = value("p4a.branch")
    if p4a_branch != PINNED_P4A_BRANCH:
        errors.append(
            f"p4a.branch must be {PINNED_P4A_BRANCH!r}, got {p4a_branch!r}"
        )

    p4a_commit = value("p4a.commit")
    if p4a_commit != PINNED_P4A_COMMIT or not re.fullmatch(
        r"[0-9a-f]{40}", p4a_commit
    ):
        errors.append(
            "p4a.commit must pin the approved API 36 toolchain commit "
            f"{PINNED_P4A_COMMIT}"
        )

    archs = {arch.strip() for arch in value("android.archs").split(",")}
    if "arm64-v8a" not in archs:
        errors.append("android.archs must include arm64-v8a for Google Play")

    artifact = value("android.release_artifact")
    if artifact != "aab":
        errors.append(f"android.release_artifact must be 'aab', got {artifact!r}")

    version_code_text = value("android.numeric_version")
    try:
        version_code = int(version_code_text)
    except ValueError:
        errors.append(
            "android.numeric_version must be an integer, "
            f"got {version_code_text!r}"
        )
        version_code = 0
    if version_code < MIN_VERSION_CODE:
        errors.append(f"android.numeric_version must be at least {MIN_VERSION_CODE}")

    if errors:
        print("Android configuration check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        "Android configuration OK: "
        f"target API {target_api}, min API {min_api_text}, NDK r{ndk}, "
        f"python-for-android {p4a_commit[:8]}, version code {version_code}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
