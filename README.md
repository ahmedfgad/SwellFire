# Swellfire

Swellfire is a cross-platform mobile game written in Python with the [Kivy](https://kivy.org) framework. It is an auto-runner shooter in the squad-multiplier genre: your character runs forward automatically, you steer left and right, gates multiply or shrink your squad, and waves of enemies fall to a hail of auto-fire from the crowd.

It is the second cross-platform Kivy game by Ahmed Gad, following [CoinTex](https://github.com/ahmedfgad/CoinTex). Swellfire mirrors CoinTex's build, packaging and screen-flow tooling — the same one codebase runs on Windows, Linux, macOS, Android and iPhone.

> **Status: under construction.** The build tooling, project layout and meta-screen scaffolding are in place (milestone M0). Gameplay, audio, levels and assets land in milestones M1–M15 — see [the plan](#plan-and-milestones).

## Contents

- [Get the game](#get-the-game)
- [How to play](#how-to-play)
- [Plan and milestones](#plan-and-milestones)
- [Run from source](#run-from-source)
- [Build the apps](#build-the-apps)
- [Project layout](#project-layout)
- [Author](#author)

## Get the game

The Android edition is the current public mobile release. The iPhone/iPad edition is prepared for App Store signing and submission but is not published yet. The [unsigned iOS workflow](IOS_BUILD_WORKFLOW.md) remains available for testing; see the [App Store release guide](APP_STORE_RELEASE.md) for publication.

## How to play

Auto-forward motion; you control only lateral movement and (eventually) which gate to pass through.

- Drag left/right to steer; release to coast.
- Gates appear in pairs ahead. The one you pass through applies its effect to your squad: `×2` doubles the crowd, `+5` adds five, `SHOTGUN` swaps your weapon.
- Enemy waves stream toward you. Your whole squad auto-fires at the nearest target.
- Squad members are lost on contact with enemies or hazards. Reach the boss at the end of each world with as many runners as possible.

Detailed gameplay rules will appear here as milestones land.

## Plan and milestones

The full implementation plan — context, locked design decisions, rendering architecture, file layout, build/packaging port plan, asset pipeline, and a 16-milestone roadmap with per-milestone tests — is at:

```
/home/ahmed-gad/.claude/plans/claude-code-prompt-fancy-dawn.md
```

Each milestone leaves a runnable desktop build:

| Milestone | Status | What it adds |
|---|---|---|
| **M0** | ✅ done | Build scripts ported from CoinTex; empty Kivy app; CI workflows |
| M1 | — | Meta screens (menu, world-map, level-select, settings, about, guide, tutorial, autoplay tuning, multiplayer host/join) |
| M2 | — | Audio manager and placeholder music/SFX |
| M3 | — | Rendering proof-of-concept (Mesh batching + atlas + 500-entity stress test) |
| M4 | — | Auto-scroll world + hero widget + free-drag-with-lane-gravity input |
| M5 | — | Pooled enemies with chase FSM, Mesh-batched |
| M6 | — | Weapons registry, auto-fire, projectiles, hit effects |
| M7 | — | Gates: spawn, pass-through detection, effects |
| M8 | — | Squad multiplier mechanic |
| M9 | — | Procedural levels (CoinTex pattern) + star scoring |
| M10 | — | Boss waves per world |
| M11 | — | Polish: ragdoll-approximate deaths, screen shake, muzzle flash |
| M12 | — | Autoplay GA (ported from CoinTex) |
| M13 | — | Networked versus (both runners visible on each device) |
| M14 | — | Asset pass: AI-generated character sprites + CC0 UI/particles |
| M15 | ✅ done | CI builds on every platform (desktop matrix, Android, iOS) + tag-triggered release |

## Run from source

You need Python 3.12. Swellfire is developed against Kivy 2.3.1.

```
git clone https://github.com/ahmedfgad/Swellfire.git
cd Swellfire
python -m pip install -r requirements.txt
python main.py
```

On Linux you can instead run `./setup_venv.sh`, which creates a virtual environment, installs Kivy and the desktop libraries it needs, and also sets up the Android build tools so the same machine can build the Android package.

If your machine has no working audio output (some virtual machines), start the game with `SDL_AUDIODRIVER=dummy python main.py` so the audio backend does not block.

## Build the apps

### Android

The Android app is built with [Buildozer](https://github.com/kivy/buildozer) using the settings in `buildozer.spec`. The helper script builds the signed release files:

```
./build_android.sh
```

The checked-in configuration targets Android 16 (API 36), uses NDK r28c and
pins the python-for-android packaging toolchain. It also protects the
portrait game layout, preserves in-app Back navigation under API 36, excludes
test code from the package, and applies safe-area spacing for edge-to-edge
displays. To validate those Play-critical settings without downloading an SDK, building, or signing anything, run:

```
./build_android.sh --check
```

A full release build produces an `.aab` for Google Play and an `.apk` for
testing in the `bin` folder. Signing the release is described in
[SIGNING.md](SIGNING.md).

### iPhone

iOS apps must be built on a Mac. The Xcode 26 GitHub workflows can create either an unsigned test IPA (`ios-build.yml`) or, after Apple credentials are configured, a signed App Store archive (`ios-app-store.yml`). If you have a Mac, `build_ios.sh` generates the configured Xcode project locally. Run `./build_ios.sh --check` anywhere for a no-build validation. See [IOS_BUILD_WORKFLOW.md](IOS_BUILD_WORKFLOW.md) and [APP_STORE_RELEASE.md](APP_STORE_RELEASE.md).

### Desktop (Windows, Linux, macOS)

`build_desktop.sh` packages the game into a standalone program with [PyInstaller](https://pyinstaller.org). PyInstaller builds for the system it runs on, so run it on each target:

```
./build_desktop.sh            # one standalone file in dist/
./build_desktop.sh --onedir   # a folder that starts faster
```

On Windows, run it inside Git Bash or MSYS2 to get `dist\Swellfire.exe`. On Linux you get `dist/Swellfire` and on macOS `dist/Swellfire.app`. A Windows `.exe` cannot be built from Linux, since PyInstaller does not cross build.

## Project layout

| Path | What it is |
| --- | --- |
| `main.py` | The app, the screen manager and the 60 Hz game loop. |
| `ui.py` | All meta screens — menu, world-map, level-select, settings, about, guide, tutorial, autoplay tuning, multiplayer host/join. *(M1)* |
| `graphics.py` | Mesh-batched sprite renderer, sprite-atlas loader, particle system. *(M3)* |
| `entities.py` | Pooled enemy / projectile / squad-runner classes; spatial-grid broad-phase. *(M5)* |
| `gates.py` | Gate spawning and effect application. *(M7)* |
| `weapons.py` | Weapon registry — pistol, rifle, shotgun, sniper. *(M6)* |
| `levels.py` | Procedural levels — `build_levels()` generates every level from per-world knobs. *(M9)* |
| `audio.py` | Music and sound-effects manager. *(M2)* |
| `state.py` | Saved progress, stars, settings, coin balance, weapon unlocks. *(M1)* |
| `autoplay.py` | In-game genetic algorithm that plays the game by itself. *(M12)* |
| `net.py` | TCP host/client for 2-player networked versus. *(M13)* |
| `assets/` | Sprite atlases, music, SFX, UI icons. Placeholder until M14. |
| `tools/` | Scripts for atlas packing, AI sprite generation, and difficulty validation. |
| `PlayerGA/` | Research version of the auto-player that searches with PyGAD. *(M12)* |
| `buildozer.spec`, `build_android.sh`, `build_desktop.sh`, `build_ios.sh`, `setup_venv.sh` | Build & packaging — ported from CoinTex. |
| `.github/workflows/` | GitHub Actions: `desktop-ci.yml` (per-push smoke), `desktop-build.yml` / `android-build.yml` / `ios-build.yml` (per-platform builds), `release.yml` (tag → all-platform GitHub Release). See `docs/CI.md`. |

## Media

Marketing & store assets live in [`swellfire_media/`](swellfire_media/) — app icon,
splash, Google Play screenshots (phone + tablet), feature graphic, YouTube cover,
and three videos (long autoplay, promo, vertical short). The graphics derive from
hand-authored art + the game's own sprites; the videos are captured from the running
game with its own music/SFX. Everything is reproducible via `tools/` — see
[`swellfire_media/README.md`](swellfire_media/README.md) for the regen commands.
Store names, descriptions, privacy answers, release copy, and asset locations
are indexed in [`STORE_METADATA.md`](STORE_METADATA.md).
Dev-only deps: `venv/bin/pip install -r requirements-media.txt` (plus `xvfb` for
portrait gameplay capture).

## Author

Ahmed Fawzy Gad

- Email: [ahmed.f.gad@gmail.com](mailto:ahmed.f.gad@gmail.com)
- LinkedIn: [linkedin.com/in/ahmedfgad](https://www.linkedin.com/in/ahmedfgad)
- GitHub: [github.com/ahmedfgad](https://github.com/ahmedfgad)
- Companion project: [CoinTex](https://github.com/ahmedfgad/CoinTex)
