#!/usr/bin/env python3
"""Apply Swellfire's checked-in App Store settings to a kivy-ios project."""

from __future__ import annotations

import argparse
import plistlib
import re
import shlex
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "ios" / "app.env"
PRIVACY_MANIFEST = ROOT / "ios" / "PrivacyInfo.xcprivacy"

REQUIRED_KEYS = {
    "IOS_APP_NAME",
    "IOS_BUNDLE_ID",
    "IOS_MARKETING_VERSION",
    "IOS_BUILD_NUMBER",
    "IOS_DEPLOYMENT_TARGET",
    "IOS_TARGETED_DEVICE_FAMILY",
    "IOS_MIN_XCODE_MAJOR",
    "IOS_COPYRIGHT",
}

# Stable, project-local IDs used only for the privacy-manifest resource.
PRIVACY_FILE_ID = "5357454C4C50524956303031"
PRIVACY_BUILD_ID = "5357454C4C50524956303032"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected KEY=value")
        key, raw_value = line.split("=", 1)
        parts = shlex.split(raw_value, comments=False, posix=True)
        if len(parts) != 1:
            raise ValueError(f"{path}:{number}: expected one shell-safe value")
        values[key.strip()] = parts[0]
    missing = sorted(REQUIRED_KEYS - values.keys())
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    return values


def validate_config(config: dict[str, str]) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9-]+)+", config["IOS_BUNDLE_ID"]):
        raise ValueError("IOS_BUNDLE_ID is not a reverse-DNS identifier")
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", config["IOS_MARKETING_VERSION"]):
        raise ValueError("IOS_MARKETING_VERSION must contain one to three numeric components")
    if not re.fullmatch(r"[1-9]\d*", config["IOS_BUILD_NUMBER"]):
        raise ValueError("IOS_BUILD_NUMBER must be a positive integer")
    if not re.fullmatch(r"\d+(?:\.\d+)?", config["IOS_DEPLOYMENT_TARGET"]):
        raise ValueError("IOS_DEPLOYMENT_TARGET must be numeric")
    if config["IOS_TARGETED_DEVICE_FAMILY"] != "1,2":
        raise ValueError("Swellfire's App Store target must remain universal (iPhone and iPad)")
    if int(config["IOS_MIN_XCODE_MAJOR"]) < 26:
        raise ValueError("App Store uploads require Xcode 26 or newer")


def _set_build_setting(body: str, key: str, value: str) -> str:
    setting = re.compile(rf"^([ \t]*){re.escape(key)}\s*=.*?;[ \t]*$", re.MULTILINE)
    match = setting.search(body)
    if match:
        return setting.sub(rf"\g<1>{key} = {value};", body, count=1)
    indent_match = re.search(r"^([ \t]+)[A-Z][A-Z0-9_]*(?:\[[^]]+\])?\s*=", body, re.MULTILINE)
    indent = indent_match.group(1) if indent_match else "\t\t\t\t"
    if body and not body.endswith("\n"):
        body += "\n"
    return body + f"{indent}{key} = {value};\n"


def _remove_build_setting(body: str, key: str) -> str:
    pattern = re.compile(
        rf"^[ \t]*(?:\"?{re.escape(key)}(?:\[[^]]+\])?\"?)\s*=.*?;[ \t]*\n?",
        re.MULTILINE,
    )
    return pattern.sub("", body)


def configure_build_settings(text: str, config: dict[str, str]) -> str:
    block_pattern = re.compile(
        r"(?P<prefix>^[ \t]*buildSettings = \{\n)(?P<body>.*?)(?P<suffix>^[ \t]*\};)",
        re.MULTILINE | re.DOTALL,
    )
    configured = 0

    def update(match: re.Match[str]) -> str:
        nonlocal configured
        body = match.group("body")
        if "INFOPLIST_FILE" not in body:
            return match.group(0)
        configured += 1
        for obsolete in (
            "CODE_SIGN_IDENTITY",
            "CODE_SIGN_RESOURCE_RULES_PATH",
            "PROVISIONING_PROFILE",
        ):
            body = _remove_build_setting(body, obsolete)
        settings = {
            "CODE_SIGN_STYLE": "Automatic",
            "CURRENT_PROJECT_VERSION": config["IOS_BUILD_NUMBER"],
            "IPHONEOS_DEPLOYMENT_TARGET": config["IOS_DEPLOYMENT_TARGET"],
            "MARKETING_VERSION": config["IOS_MARKETING_VERSION"],
            "PRODUCT_BUNDLE_IDENTIFIER": config["IOS_BUNDLE_ID"],
            "SUPPORTS_MACCATALYST": "NO",
            "TARGETED_DEVICE_FAMILY": f'"{config["IOS_TARGETED_DEVICE_FAMILY"]}"',
        }
        for key, value in settings.items():
            body = _set_build_setting(body, key, value)
        return match.group("prefix") + body + match.group("suffix")

    result = block_pattern.sub(update, text)
    if configured < 2:
        raise ValueError(f"expected at least two app-target build configurations, found {configured}")
    return result


def add_privacy_resource(text: str) -> str:
    if "PrivacyInfo.xcprivacy in Resources" not in text:
        anchor = "/* End PBXBuildFile section */"
        line = (
            f"\t\t{PRIVACY_BUILD_ID} /* PrivacyInfo.xcprivacy in Resources */ = "
            f"{{isa = PBXBuildFile; fileRef = {PRIVACY_FILE_ID} /* PrivacyInfo.xcprivacy */; }};\n"
        )
        if anchor not in text:
            raise ValueError("PBXBuildFile section not found")
        text = text.replace(anchor, line + anchor, 1)

    # The build-file entry above also contains the file-reference identifier,
    # so checking for the identifier alone can produce a dangling reference.
    if "path = PrivacyInfo.xcprivacy" not in text:
        anchor = "/* End PBXFileReference section */"
        line = (
            f"\t\t{PRIVACY_FILE_ID} /* PrivacyInfo.xcprivacy */ = "
            "{isa = PBXFileReference; lastKnownFileType = text.xml; "
            "path = PrivacyInfo.xcprivacy; sourceTree = \"<group>\"; };\n"
        )
        if anchor not in text:
            raise ValueError("PBXFileReference section not found")
        text = text.replace(anchor, line + anchor, 1)

    group_section = re.search(
        r"/\* Begin PBXGroup section \*/(?P<body>.*?)/\* End PBXGroup section \*/",
        text,
        re.DOTALL,
    )
    if not group_section:
        raise ValueError("PBXGroup section not found")
    group_body = group_section.group("body")
    if "PrivacyInfo.xcprivacy */," not in group_body:
        info_line = re.search(
            r"^(?P<indent>[ \t]*)[A-Fa-f0-9]+ /\* .*?-Info\.plist \*/,\s*$",
            group_body,
            re.MULTILINE,
        )
        if not info_line:
            raise ValueError("Info.plist resource-group entry not found")
        insertion = (
            info_line.group(0)
            + "\n"
            + info_line.group("indent")
            + f"{PRIVACY_FILE_ID} /* PrivacyInfo.xcprivacy */,")
        group_body = group_body[: info_line.start()] + insertion + group_body[info_line.end() :]
        text = text[: group_section.start("body")] + group_body + text[group_section.end("body") :]

    phase_section = re.search(
        r"/\* Begin PBXResourcesBuildPhase section \*/(?P<body>.*?)/\* End PBXResourcesBuildPhase section \*/",
        text,
        re.DOTALL,
    )
    if not phase_section:
        raise ValueError("PBXResourcesBuildPhase section not found")
    phase_body = phase_section.group("body")
    if "PrivacyInfo.xcprivacy in Resources */," not in phase_body:
        files = re.search(
            r"(?P<prefix>files = \(\n)(?P<body>.*?)(?P<suffix>^[ \t]*\);)",
            phase_body,
            re.MULTILINE | re.DOTALL,
        )
        if not files:
            raise ValueError("resources build-phase file list not found")
        existing = files.group("body")
        indent_match = re.search(r"^([ \t]+)[A-Fa-f0-9]+", existing, re.MULTILINE)
        indent = indent_match.group(1) if indent_match else "\t\t\t\t"
        updated_files = (
            files.group("prefix")
            + existing
            + indent
            + f"{PRIVACY_BUILD_ID} /* PrivacyInfo.xcprivacy in Resources */,\n"
            + files.group("suffix")
        )
        phase_body = phase_body[: files.start()] + updated_files + phase_body[files.end() :]
        text = text[: phase_section.start("body")] + phase_body + text[phase_section.end("body") :]

    return text


def configure_info_plist(path: Path, config: dict[str, str]) -> None:
    with path.open("rb") as stream:
        info = plistlib.load(stream)
    info.update(
        {
            "CFBundleDisplayName": config["IOS_APP_NAME"],
            "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
            "CFBundleName": config["IOS_APP_NAME"],
            "CFBundleShortVersionString": "$(MARKETING_VERSION)",
            "CFBundleVersion": "$(CURRENT_PROJECT_VERSION)",
            "ITSAppUsesNonExemptEncryption": False,
            "NSHumanReadableCopyright": config["IOS_COPYRIGHT"],
            "NSLocalNetworkUsageDescription": (
                "Swellfire uses your local network only when you host or join a two-player game."
            ),
            "UIRequiresFullScreen": True,
            "UISupportedInterfaceOrientations": ["UIInterfaceOrientationPortrait"],
            "UISupportedInterfaceOrientations~ipad": ["UIInterfaceOrientationPortrait"],
        }
    )
    # The asset catalog is the authoritative icon declaration.
    info.pop("CFBundleIcons", None)
    with path.open("wb") as stream:
        plistlib.dump(info, stream, sort_keys=False)


def configure_project(project_dir: Path, config: dict[str, str]) -> tuple[Path, Path]:
    xcode_projects = list(project_dir.glob("*.xcodeproj"))
    if len(xcode_projects) != 1:
        raise ValueError(f"expected one .xcodeproj in {project_dir}, found {len(xcode_projects)}")
    info_plists = list(project_dir.glob("*-Info.plist"))
    if len(info_plists) != 1:
        raise ValueError(f"expected one app Info.plist in {project_dir}, found {len(info_plists)}")

    project_file = xcode_projects[0] / "project.pbxproj"
    project_text = project_file.read_text(encoding="utf-8")
    project_text = configure_build_settings(project_text, config)
    project_text = add_privacy_resource(project_text)
    project_file.write_text(project_text, encoding="utf-8")

    configure_info_plist(info_plists[0], config)
    shutil.copyfile(PRIVACY_MANIFEST, project_dir / PRIVACY_MANIFEST.name)
    return xcode_projects[0], info_plists[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--build-number", help="override IOS_BUILD_NUMBER for this generated project")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.build_number is not None:
        config["IOS_BUILD_NUMBER"] = args.build_number
    validate_config(config)
    project, plist = configure_project(args.project_dir.resolve(), config)
    print(f"Configured {project}")
    print(f"Configured {plist}")
    print(f"Bundle ID: {config['IOS_BUNDLE_ID']}")
    print(f"Version: {config['IOS_MARKETING_VERSION']} ({config['IOS_BUILD_NUMBER']})")


if __name__ == "__main__":
    main()
