[app]

# Title of the application.
title = GateRunner

# Package name and domain. Together they form the application id
# com.ahmedgad.gaterunner. Keep these consistent across builds or Google Play
# will treat the build as a different app.
package.name = gaterunner
package.domain = com.ahmedgad

# Folder that holds main.py.
source.dir = .

# File types to include in the package. The asset pipeline ships PNG atlases
# and their JSON UV maps; the Mesh renderer reads both at runtime.
source.include_exts = py,png,wav,json,atlas

# Folders to leave out of the package. PlayerGA is the research version of the
# auto-player and pulls in pygad+numpy. tools/ is dev-only.
source.exclude_dirs = bin, dist, build, venv, .venv, .buildozer, .git, __pycache__, PlayerGA, tools, assets/raw

# Version shown to users.
version = 1.0

# Packages the app needs. Networking uses the Python standard library.
requirements = python3,kivy

# The 2-player feature opens a network connection between the two devices.
android.permissions = INTERNET

# Splash image shown while the app starts.
presplash.filename = %(source.dir)s/presplash.png

# App icon.
icon.filename = %(source.dir)s/icon.png

# Screen orientation.
orientation = landscape

# Run the app full screen.
fullscreen = 1


# Android settings

# Target Android version. Google Play requires updates to target API 35.
android.api = 35

# Lowest Android version the app runs on. python-for-android needs 21 or higher.
android.minapi = 21

# Build for 64-bit and 32-bit. Google Play requires the 64-bit arm64-v8a.
android.archs = arm64-v8a, armeabi-v7a

# Accept the Android SDK licenses so the build does not stop to ask.
android.accept_sdk_license = True

# Release file to build: aab or apk. The Play Store upload uses the aab.
# build_android.sh switches this when it also builds the apk for testing.
android.release_artifact = aab

# Version code. It must be higher than the version code already on Google Play,
# or the upload is rejected. Increment by 1 (or by 100 to leave room for hot
# fixes) for each release.
android.numeric_version = 10000

# Background color of the splash screen.
android.presplash_color = #000000

# Release signing is passed in by build_android.sh through the P4A_RELEASE_KEYSTORE
# environment variables, so no keystore is written here.


[buildozer]

# Log level. 2 shows full command output.
log_level = 2

# Warn if buildozer runs as root.
warn_on_root = 1
