# Building and archiving Swellfire for iOS

iOS apps must be built on a Mac. This project uses Xcode 26 GitHub Actions runners, so you do not need to own one. The unsigned test workflow needs no Apple credentials; App Store signing is a separate manual workflow.

The workflow file is `.github/workflows/ios-build.yml`. This document explains how to run it and where the built files appear.

## Before the first run

GitHub only runs workflows that are pushed to the repository. Commit and push the workflow file once:

```
git add .github/workflows/ios-build.yml
git commit -m "Add iOS build workflow"
git push
```

## Run the workflow

1. Open the repository on GitHub in a web browser.
2. Click the **Actions** tab.
3. In the list on the left, click **Build iOS app**.
4. Click the **Run workflow** button on the right. Leave the branch on `main` and click the green **Run workflow** button.

The run starts in a few seconds and shows up in the list.

The combined `Release` workflow can also call this unsigned build. It does not create a signed App Store artifact.

## How long it takes

The first run takes about 45 to 90 minutes, because it builds the Python and Kivy toolchain from source. Later runs are faster, because that toolchain is cached.

## Where the files are created

When the run finishes with a green check mark:

1. Click the finished run in the **Actions** tab.
2. Scroll to the **Artifacts** section at the bottom of the run summary page.
3. You will see two items:
   - **Swellfire-unsigned-ipa**: download it. It arrives as a zip. Unzip it to get `Swellfire-unsigned.ipa`. This is the file you install on an iPhone.
   - **Swellfire-xcode-project**: the configured Xcode project, including the App Store identity, icons, privacy manifest, and version settings.

GitHub keeps these artifacts for 30 days. After that, run the workflow again to get fresh files.

## Install it on an iPhone

Use `Swellfire-unsigned.ipa` with the steps in `docs/platforms/ios-install.md`.

## Create an App Store archive

After joining the Apple Developer Program and configuring the four protected
signing secrets, manually run **Archive iOS for App Store**. It creates and
validates a signed IPA and xcarchive but does not upload them to Apple. Follow
the complete account, signing, TestFlight, metadata, privacy, screenshot, and
submission checklist in `docs/release/app-store.md`.

## If a run fails

1. Open the failed run and read the step shown in red.
2. Do not downgrade the runner: App Store uploads now require Xcode 26 and the
   iOS 26 SDK, enforced by the workflow.
3. To rebuild the toolchain from scratch, change the cache-key suffix from `v1`
   to `v2`, or delete the cache from the Actions cache list.
4. Run `./scripts/build_ios.sh --check` locally for fast configuration validation.
