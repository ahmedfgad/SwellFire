# Continuous integration

Swellfire's GitHub Actions workflows live in `.github/workflows/`. There are two
tiers: a fast smoke test that runs on every push, and the real per-platform
builds that run on demand or when a version tag is pushed.

| Workflow | File | Trigger | What it does |
| --- | --- | --- | --- |
| Desktop CI | `desktop-ci.yml` | every push and PR | Installs deps, byte-compiles, boots the app headless under xvfb. |
| Build desktop apps | `desktop-build.yml` | manual + release | PyInstaller binaries for Linux, Windows and macOS, one artifact each. |
| Build Android app | `android-build.yml` | manual + release | Buildozer debug `.apk` artifact. |
| Build iOS app | `ios-build.yml` | manual + release | Unsigned `.ipa` and the Xcode project on a macOS runner. |
| Release | `release.yml` | `v*` tags | Runs the three build workflows and attaches every artifact to one GitHub Release. |

## Per-push smoke (`desktop-ci.yml`)

Runs on every push and pull request against `main`/`master`. It installs the
requirements on a clean Ubuntu runner, byte-compiles every `.py` (catching
syntax errors), and boots `main.py` under xvfb for a few seconds (catching
import errors and first-frame crashes). It deliberately does **not** package
anything — it is the cheap gate that catches the regressions a 30–90 minute
buildozer / kivy-ios build would otherwise only surface much later.

## Platform builds (on demand)

`desktop-build.yml`, `android-build.yml` and `ios-build.yml` run the real
packaging for each platform. They are **not** run on every push — that would
burn CI minutes (the Android toolchain build alone is 30–60 minutes). Run one
from the Actions tab with **Run workflow** (`workflow_dispatch`), or let
`release.yml` run them all on a version tag.

- **desktop-build.yml** — a Linux/Windows/macOS matrix that runs
  `build_desktop.sh` (PyInstaller) on each OS and uploads the binary
  (`Swellfire-linux`, `Swellfire-windows`, `Swellfire-macos`). The Linux job
  also boots the packaged binary from a foreign cwd under xvfb to catch the
  packaged-asset-path class of bugs (see CLAUDE.md) that source-tree runs miss.
- **android-build.yml** — runs `buildozer android debug` (the same thing as
  `build_android.sh --debug`, reading the shared `buildozer.spec`) and uploads
  an unsigned `.apk`. No secrets needed; the signed Play `.aab` is built
  locally. The SDK/NDK are cached, keyed on `buildozer.spec`.
- **ios-build.yml** — unsigned `.ipa` plus the Xcode project on a macOS runner.
  Full notes in `IOS_BUILD_WORKFLOW.md`.

## Releases (tag-triggered)

Push a version tag and `release.yml` builds every platform and gathers the
artifacts into a single GitHub Release for that tag:

```
git tag v1.0 && git push origin v1.0
```

It reuses the three build workflows via `uses:` (no duplicated build logic), so
each platform also stays independently runnable from the Actions tab. The build
workflows themselves expose `workflow_call` and no longer trigger on tags, so a
tag fires `release.yml` only — nothing builds twice.

The signed Google Play `.aab` is intentionally **not** built in CI: it needs the
private upload keystore, which must never live in a workflow. Build it locally
with `./build_android.sh`. See `SIGNING.md`.

## Local builds

The build scripts that CI wraps are documented in the project `README.md`:
`build_desktop.sh`, `build_android.sh`, `build_ios.sh`. CI runs the same scripts
and the shared `buildozer.spec`, so a green local build is a good predictor of a
green CI build.
