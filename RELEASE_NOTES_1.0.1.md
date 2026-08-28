# Swellfire 1.0.1

This update keeps Swellfire current on Android and makes play more dependable
across phones, tablets and desktop systems.

## What changed

- Updated the Android target to API 36 and refreshed the Android build
  toolchain for Android 16 and 16 KB memory-page compatibility.
- Improved edge-to-edge and safe-area spacing so the gameplay HUD stays clear
  of system bars, notches and Dynamic Island areas.
- Reworked the booster bar and pause controls with larger, more reliable touch
  targets.
- Added consistent Back and Escape behavior for gameplay, dialogs, menus,
  tutorials and multiplayer screens.
- Fixed background/resume handling so an active run pauses safely, progress is
  checkpointed and audio resumes in the correct state.
- Fixed delayed level dialogs appearing after a player had already left or
  restarted a run.
- Booster use is now saved immediately, preventing consumed items from being
  restored after closing the app.
- Hardened saved-game recovery, shop transactions and malformed multiplayer
  messages.
- Improved multiplayer address validation, connection feedback and disconnect
  cleanup.
- Added the iPhone/iPad App Store configuration, privacy manifest and release
  preparation files for the upcoming iOS edition.

## Downloads

- `Swellfire-1.0.1-android.apk` is the signed Android release APK.
- `Swellfire-1.0.1-linux-x86_64` is the standalone 64-bit Linux application.
- `Swellfire-1.0.1-windows-x86_64.exe` is the standalone 64-bit Windows
  application.
- `Swellfire-1.0.1-macos-arm64.zip` contains the app for Apple Silicon Macs.
- `Swellfire-1.0.1-ios-unsigned.ipa` is the unsigned iPhone and iPad build for
  developer signing and testing. It cannot be installed or submitted to the
  App Store until it is signed with an Apple Developer account.

The Linux download may need executable permission after downloading:
`chmod +x Swellfire-1.0.1-linux-x86_64`.

The macOS app is not Developer ID signed or notarized, so macOS may show a
Gatekeeper warning when it is opened for the first time.
