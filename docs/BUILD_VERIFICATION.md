# Build verification (M15)

M15 is "build verification on every platform": the game packages and launches
on Windows, macOS, Linux, Android and iOS, with the builds driven by CI so they
stay reproducible. This document tracks what is automated and how to run it.

## Platform matrix

| Platform | Build method | Automated? | Workflow | Notes |
| --- | --- | --- | --- | --- |
| Linux (desktop) | `scripts/build_desktop.sh` + PyInstaller | ✅ full build + boot | `desktop-build.yml` | Onefile binary; also boots from a foreign cwd under xvfb. Boot-only smoke on every push via `desktop-ci.yml`. |
| Windows (desktop) | `scripts/build_desktop.sh` + PyInstaller | ✅ full build | `desktop-build.yml` | `Swellfire.exe` on a `windows-latest` runner. |
| macOS (desktop) | `scripts/build_desktop.sh` + PyInstaller | ✅ full build | `desktop-build.yml` | `Swellfire.app` (zipped with `ditto`) on a `macos-14` runner. |
| Android | `buildozer android debug` | ✅ full build | `android-build.yml` | Unsigned debug `.apk`. Signed Play `.aab` stays local. |
| iOS | kivy-ios + Xcode 26 | ✅ unsigned build; signed archive ready | `ios-build.yml`, `ios-app-store.yml` | Universal iPhone/iPad; signed workflow requires Apple secrets. |
| Web (optional) | — | ❌ | — | Out of scope unless requested. |

## What M15 adds

The M15 work fills the gaps in the matrix above:

1. A desktop build matrix (Linux, Windows, macOS) that runs the real PyInstaller
   build and uploads each platform's binary as an artifact
   (`desktop-build.yml`). The Linux job also boots the packaged binary from a
   foreign cwd to catch packaged-asset-path bugs.
2. An Android build job that runs buildozer and uploads the `.apk`
   (`android-build.yml`).
3. A combined release workflow, tag-triggered, that runs all three build
   workflows and gathers every platform's artifact into one GitHub Release
   (`release.yml`).

The iOS half was already done (`ios-build.yml`); it is now reusable via
`workflow_call` so the release workflow can fold it in without building twice.

## Running the builds

| Goal | How |
| --- | --- |
| Build one platform on demand | Actions tab → pick the workflow → **Run workflow** |
| Build everything and publish a release | `git tag v1.0 && git push origin v1.0` |
| Build locally | `scripts/build_desktop.sh`, `scripts/build_android.sh`, `scripts/build_ios.sh` (see README) |

## Verification status

- **Linux desktop** — verified locally: `scripts/build_desktop.sh` produces a working
  onefile `dist/Swellfire` that boots cleanly from a foreign cwd
  (`cd /tmp && SDL_AUDIODRIVER=dummy <path>/dist/Swellfire`), exercising the
  exact smoke step `desktop-build.yml` runs.
- **Windows / macOS / Android / iOS** — the workflow YAML is validated and the
  build logic mirrors the locally-verified scripts and the shared
  `buildozer.spec`, but these have not yet been confirmed by a live green run on
  GitHub. Record real "last verified" dates here after the first run of each on
  the remote.
