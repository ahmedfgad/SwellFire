[app]

# Title of the application.
title = Swellfire

# Package name and domain. Together they form the application id
# com.vilvik.swellfire. Keep these consistent across builds or Google Play
# will treat the build as a different app.
package.name = swellfire
package.domain = com.vilvik

# Folder that holds main.py.
source.dir = .

# File types to include in the package. The asset pipeline ships PNG atlases
# and their JSON UV maps; the Mesh renderer reads both at runtime.
source.include_exts = py,png,wav,json,atlas

# Folders to leave out of the package. PlayerGA is the research version of the
# auto-player and pulls in pygad+numpy. tools/ is dev-only.
source.exclude_dirs = bin, dist, build, venv, .venv, .buildozer, .git, __pycache__, PlayerGA, tools, tests, scripts, docs, requirements, assets/raw, marketing

# Keep stray regression-test modules out as a defense in depth.
source.exclude_patterns = test_*.py

# Version shown to users.
version = 1.0.2

# Packages the app needs. Networking uses the Python standard library.
requirements = python3,kivy,certifi

# The 2-player feature opens a network connection between the two devices.
android.permissions = INTERNET

# Splash image shown while the app starts.
presplash.filename = %(source.dir)s/presplash.png

# App icon.
icon.filename = %(source.dir)s/icon.png

# Screen orientation.
orientation = portrait

# Run the app full screen. Android 16 enforces edge-to-edge, so the Kivy HUD
# applies its persisted safe-area inset to every top control.
fullscreen = 1

# The pinned Kivy/SDL activity still consumes legacy Back key events. API 36
# otherwise stops dispatching those events when predictive Back is enabled, so
# use Android's documented temporary migration opt-out. appCategory=game is
# semantically correct and preserves the portrait-first game layout on large
# Android 16 screens while the shared Kivy UI remains freely resizable.
android.extra_manifest_application_arguments = android/manifest_application_attributes.xml


# Android settings

# Compile against and target Android 16. Google Play requires API 36 for app
# updates starting August 31, 2026. This does not change the minimum Android
# version supported below.
android.api = 36

# Lowest Android version the app runs on. python-for-android needs 21 or higher.
android.minapi = 21

# Use the NDK recommended by python-for-android's 2026 release. NDK r28c also
# emits native libraries that are compatible with Android's 16 KB page sizes.
android.ndk = 28c
android.ndk_api = 21

# API 36 support depends on the modern python-for-android toolchain. Keep the
# upstream branch that contains the signed v2026.05.09 release commit selected,
# then pin the exact checkout so local and CI builds are reproducible.
p4a.branch = master
p4a.commit = 58d21141f17c889bf8585f5665921d72028f8831

# Build for 64-bit and 32-bit. Google Play requires the 64-bit arm64-v8a.
android.archs = arm64-v8a, armeabi-v7a

# Accept the Android SDK licenses so the build does not stop to ask.
android.accept_sdk_license = True

# Release file to build: aab or apk. The Play Store upload uses the aab.
# scripts/build_android.sh switches this when it also builds the apk for testing.
android.release_artifact = aab

# Version code for the API 36 compliance update, raised from 10000. It must be
# higher than the version code already on Google Play or the upload is rejected;
# confirm the live value in Play Console before building.
android.numeric_version = 10002

# Background color of the splash screen.
android.presplash_color = #000000

# Release signing is passed in by scripts/build_android.sh through the P4A_RELEASE_KEYSTORE
# environment variables, so no keystore is written here.


[buildozer]

# Log level. 2 shows full command output.
log_level = 2

# Warn if buildozer runs as root.
warn_on_root = 1
