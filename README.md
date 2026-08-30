# Swellfire

Swellfire is a cross-platform mobile game written in Python with the [Kivy](https://kivy.org) framework. It is an auto-runner shooter in the squad-multiplier genre: your character runs forward automatically, you steer left and right, gates multiply or shrink your squad, and waves of enemies fall to a hail of auto-fire from the crowd.

It is the second cross-platform Kivy game by Ahmed Gad, following [CoinTex](https://github.com/ahmedfgad/CoinTex). Swellfire mirrors CoinTex's build, packaging and screen-flow tooling — the same one codebase runs on Windows, Linux, macOS, Android and iPhone.

> Current release: 1.0.2. The shared Kivy codebase supports desktop, Android, and iOS builds.

## Contents

- [Get the game](#get-the-game)
- [How to play](#how-to-play)
- [Design history](#design-history)
- [Run from source](#run-from-source)
- [Test changes](#test-changes)
- [Build the apps](#build-the-apps)
- [Project layout](#project-layout)
- [Author](#author)

## Get the game

The Android edition is the current public mobile release. The iPhone/iPad edition is prepared for App Store signing and submission but is not published yet. The [unsigned iOS workflow](docs/platforms/ios-build-workflow.md) remains available for testing; see the [App Store release guide](docs/release/app-store.md) for publication.

## How to play

Auto-forward motion; you control only lateral movement and (eventually) which gate to pass through.

- Drag left/right to steer; release to coast.
- Gates appear in pairs ahead. The one you pass through applies its effect to your squad: `×2` doubles the crowd, `+5` adds five, `SHOTGUN` swaps your weapon.
- Enemy waves stream toward you. Your whole squad auto-fires at the nearest target.
- Squad members are lost on contact with enemies or hazards. Reach the boss at the end of each world with as many runners as possible.

Detailed gameplay rules will appear here as milestones land.

## Design history

Architecture notes, implementation plans, and the original milestone designs are retained under [`docs/superpowers/`](docs/superpowers/) as project history.

## Run from source

You need Python 3.12. Swellfire is developed against Kivy 2.3.1.

```
git clone https://github.com/ahmedfgad/Swellfire.git
cd Swellfire
python -m pip install -r requirements/base.txt
python main.py
```

On Linux you can instead run `./scripts/setup_venv.sh`, which creates a virtual environment, installs Kivy and the desktop libraries it needs, and also sets up the Android build tools so the same machine can build the Android package.

If your machine has no working audio output (some virtual machines), start the game with `SDL_AUDIODRIVER=dummy python main.py` so the audio backend does not block.

## Test changes

Install the complete development environment with `python -m pip install -r requirements/dev.txt`, then run `SDL_AUDIODRIVER=dummy python -m pytest -q`. The suite covers both gameplay code in `tests/` and asset/media tooling in `tools/tests/`.

## Build the apps

### Android

The Android app is built with [Buildozer](https://github.com/kivy/buildozer) using the settings in `buildozer.spec`. The helper script builds the signed release files:

```
./scripts/build_android.sh
```

The checked-in configuration targets Android 16 (API 36), uses NDK r28c and
pins the python-for-android packaging toolchain. It also protects the
portrait game layout, preserves in-app Back navigation under API 36, excludes
test code from the package, and applies safe-area spacing for edge-to-edge
displays. To validate those Play-critical settings without downloading an SDK, building, or signing anything, run:

```
./scripts/build_android.sh --check
```

A full release build produces an `.aab` for Google Play and an `.apk` for
testing in the `bin` folder. Signing the release is described in
[docs/platforms/android-signing.md](docs/platforms/android-signing.md).

### iPhone

iOS apps must be built on a Mac. The Xcode 26 GitHub workflows can create either an unsigned test IPA (`ios-build.yml`) or, after Apple credentials are configured, a signed App Store archive (`ios-app-store.yml`). If you have a Mac, `scripts/build_ios.sh` generates the configured Xcode project locally. Run `./scripts/build_ios.sh --check` anywhere for a no-build validation. See [docs/platforms/ios-build-workflow.md](docs/platforms/ios-build-workflow.md) and [docs/release/app-store.md](docs/release/app-store.md).

### Desktop (Windows, Linux, macOS)

`scripts/build_desktop.sh` packages the game into a standalone program with [PyInstaller](https://pyinstaller.org). PyInstaller builds for the system it runs on, so run it on each target:

```
./scripts/build_desktop.sh            # one standalone file in dist/
./scripts/build_desktop.sh --onedir   # a folder that starts faster
```

On Windows, run it inside Git Bash or MSYS2 to get `dist\Swellfire.exe`. On Linux you get `dist/Swellfire` and on macOS `dist/Swellfire.app`. A Windows `.exe` cannot be built from Linux, since PyInstaller does not cross build.

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py` | Kivy/Buildozer entry point and app lifecycle. |
| `swellfire/` | Runtime package: gameplay, UI, audio, networking, state, and rendering. |
| `tests/` | Game regression tests. |
| `assets/` | Runtime sprites, atlases, music, sound effects, and UI assets. |
| `scripts/` | Environment setup and Android, desktop, and iOS build helpers. |
| `requirements/` | Runtime, development, platform, and media dependency sets. |
| `tools/` | Asset generation, capture, media, and configuration utilities; tool tests live in `tools/tests/`. |
| `android/`, `ios/` | Platform-specific configuration and store metadata. |
| `docs/` | CI, platform, release, and historical design documentation. |
| `marketing/` | Store screenshots, promotional graphics, and videos. |
| `.github/workflows/` | Cross-platform CI and packaging workflows. |

## Media

Marketing & store assets live in [`marketing/`](marketing/) — app icon,
splash, Google Play screenshots (phone + tablet), feature graphic, YouTube cover,
and three videos (long autoplay, promo, vertical short). The graphics derive from
hand-authored art + the game's own sprites; the videos are captured from the running
game with its own music/SFX. Everything is reproducible via `tools/` — see
[`marketing/README.md`](marketing/README.md) for the regen commands.
Store names, descriptions, privacy answers, release copy, and asset locations
are indexed in [`docs/release/store-metadata.md`](docs/release/store-metadata.md).
Dev-only deps: `.venv/bin/pip install -r requirements/media.txt` (plus `xvfb` for
portrait gameplay capture).

## Author

Ahmed Fawzy Gad

- Email: [ahmed.f.gad@gmail.com](mailto:ahmed.f.gad@gmail.com)
- LinkedIn: [linkedin.com/in/ahmedfgad](https://www.linkedin.com/in/ahmedfgad)
- GitHub: [github.com/ahmedfgad](https://github.com/ahmedfgad)
- Companion project: [CoinTex](https://github.com/ahmedfgad/CoinTex)
