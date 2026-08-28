# Continuous integration

Swellfire's GitHub Actions workflows live in `.github/workflows/`. There are two
tiers: a fast smoke test that runs on every push, and the real per-platform
builds that run on demand, directly or through the manual combined release workflow.

| Workflow | File | Trigger | What it does |
| --- | --- | --- | --- |
| Desktop CI | `desktop-ci.yml` | every push and PR | Installs deps, byte-compiles, boots the app headless under xvfb. |
| Build desktop apps | `desktop-build.yml` | manual + called by Release | PyInstaller binaries for Linux, Windows and macOS, one artifact each. |
| Build Android app | `android-build.yml` | manual + called by Release | Buildozer debug `.apk` artifact. |
| Build iOS app | `ios-build.yml` | manual + called by Release | Xcode 26 unsigned `.ipa` and configured Xcode project. |
| Archive iOS for App Store | `ios-app-store.yml` | manual only | Signed, validated App Store `.ipa` and xcarchive; never uploads. |
| Release | `release.yml` | manual | Runs the three unsigned build workflows together; does not publish. |

## Per-push smoke (`desktop-ci.yml`)

Runs on every push and pull request against `main`/`master`. It installs the
requirements on a clean Ubuntu runner, validates the Play-critical Android
target/toolchain settings without building, byte-compiles every `.py` (catching
syntax errors), and boots `main.py` under xvfb for a few seconds (catching
import errors and first-frame crashes). It deliberately does **not** package
anything — it is the cheap gate that catches the regressions a 30–90 minute
buildozer / kivy-ios build would otherwise only surface much later.

## Platform builds (on demand)

`desktop-build.yml`, `android-build.yml` and `ios-build.yml` run the real
packaging for each platform. They are **not** run on every push — that would
burn CI minutes (the Android toolchain build alone is 30–60 minutes). Run one
from the Actions tab with **Run workflow** (`workflow_dispatch`), or manually
run `release.yml` to call all three in one workflow run.

- **desktop-build.yml** — a Linux/Windows/macOS matrix that runs
  `build_desktop.sh` (PyInstaller) on each OS and uploads the binary
  (`Swellfire-linux`, `Swellfire-windows`, `Swellfire-macos`). The Linux job
  also boots the packaged binary from a foreign cwd under xvfb to catch the
  packaged-asset-path class of bugs (see CLAUDE.md) that source-tree runs miss.
- **android-build.yml** — runs `buildozer android debug` (the same thing as
  `build_android.sh --debug`, reading the shared `buildozer.spec`) and uploads
  an unsigned `.apk`. It runs `tools/check_android_config.py` first so an old
  target API or packaging toolchain fails before the long build. No secrets
  needed; the signed Play `.aab` is built locally. The SDK/NDK are cached,
  keyed on `buildozer.spec`.
- **ios-build.yml** — unsigned `.ipa` plus the App Store-configured Xcode
  project on an Xcode 26 runner. **ios-app-store.yml** is a separate manual
  signing/archive workflow that requires protected Apple secrets and never
  uploads automatically. Full notes are in `IOS_BUILD_WORKFLOW.md` and
  `APP_STORE_RELEASE.md`.

## Combined release build (manual)

Run `release.yml` from the Actions tab when you want all three unsigned/public
artifacts built together. It reuses the platform workflows via `workflow_call`
and gathers their artifacts in one workflow run. It does not create a GitHub
Release, publish to either store, or sign the mobile packages; attach the
artifacts to a public release only after reviewing them.

The signed Google Play `.aab` is intentionally **not** built in CI: it needs the
private upload keystore, which must never live in a workflow. Build it locally
with `./build_android.sh`. See `SIGNING.md`.

## Local builds

The build scripts that CI wraps are documented in the project `README.md`:
`build_desktop.sh`, `build_android.sh`, `build_ios.sh`. CI runs the same scripts
and the shared `buildozer.spec`, so a green local build is a good predictor of a
green CI build.
