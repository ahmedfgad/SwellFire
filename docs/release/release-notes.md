# Swellfire 1.0

The first full release of Swellfire, a cross-platform auto-runner squad-shooter built in Python with [Kivy](https://kivy.org). Steer a running squad, pass through gates to multiply your numbers, clear enemy waves with the crowd's combined auto-fire, and take down a boss at the end of every world.

Swellfire is the second cross-platform Kivy game by Ahmed Gad, following [CoinTex](https://github.com/ahmedfgad/CoinTex). The same Python codebase runs on Windows, macOS, Linux, Android and iPhone.

## What's in 1.0

- 6 worlds, 60 levels. Meadow, Desert, Industrial, Snowfield, Volcano and Cosmos, ten levels each, with a boss fight at the end of every world.
- Squad-multiplier gates. Pass the right gate to grow the crowd (x2, +5, and so on); more runners means more firepower. Rare bonus gates hand you a weapon swap or a booster charge.
- Auto-fire combat. Your whole squad fires at the nearest enemy, so a bigger squad puts out a denser hail.
- Four weapons. Pistol, Rifle, Shotgun and Sniper, each upgradeable through four tiers in the shop.
- Six boosters. Grenade, Shield, Reinforcements, Freeze, Overdrive and Magnet, to turn a losing run around.
- Shop and coins. Earn coins as you play, then buy and upgrade weapons, boosters and squad bonuses.
- Star ratings. Three stars per level to chase, plus a progress bar that becomes a boss-petrify meter on boss levels.
- Versus multiplayer. Race a friend on a nearby device, with both squads visible on each screen and a side-by-side results comparison.
- Animated presentation. Particle bursts, screen shake, sprite flashes and smooth transitions throughout.
- Music and sound. Per-world music and a distinct cue for every action.
- Auto Player. A built-in genetic-algorithm player can run the game hands-free.

## Downloads

Desktop builds are ready to run. The mobile builds are unsigned (no Apple or Google account was needed to make them), so you install them by sideloading.

- Windows (`Swellfire-windows.exe`): download and run. Windows SmartScreen may warn on an unsigned app; choose "More info" then "Run anyway".
- macOS (`Swellfire-macos.zip`): unzip and open Swellfire.app. On first launch, right-click the app and choose Open to get past Gatekeeper.
- Linux (`Swellfire-linux`): run `chmod +x Swellfire-linux`, then start it. It is a single self-contained file.
- Android (`Swellfire-android.apk`): an unsigned debug build for sideloading. Turn on "install unknown apps" for your browser or file manager, then open the APK.
- iPhone (`Swellfire-unsigned.ipa`): sideload with [AltStore](https://altstore.io) or Sideloadly, which re-sign it with your own Apple ID. See docs/platforms/ios-install.md.
- iPhone, Xcode (`Swellfire-xcode-project.zip`): open the project on a Mac, set your team, Archive, and run on your device or upload to the App Store.

The signed Google Play `.aab` is not attached here. It needs the private upload keystore and is built separately with `./scripts/build_android.sh`.

## How to play

- The hero runs forward on its own; you only steer. Drag left or right to move, and release to coast.
- Gates come in pairs. Steer through the one you want, and its effect applies to your whole squad.
- Enemy waves stream toward you while your squad auto-fires. Runners are lost on contact with enemies and hazards.
- Reach each world's boss with as large a squad as you can, and spend booster charges to swing the fight.

## Run from source

Requires Python 3.12 (developed against Kivy 2.3.1):

```bash
git clone https://github.com/ahmedfgad/Swellfire.git
cd Swellfire
python -m pip install -r requirements/base.txt
python main.py
```

On a machine with no audio output, start with `SDL_AUDIODRIVER=dummy python main.py`.

## Notes

- The Android `.apk` and iOS `.ipa` here are unsigned on purpose, so they can be built without any developer account. They are meant for sideloading and testing, not store distribution.
- Every artifact is reproducible: `./scripts/build_desktop.sh` for Windows, macOS and Linux; `./scripts/build_android.sh` for a signed Android release; and the iOS GitHub Actions workflow. Pushing a version tag builds and publishes all platforms.

A Python and Kivy game by Ahmed Gad.
