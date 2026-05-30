# Swellfire 1.0

The first full release of **Swellfire** — a cross-platform auto-runner squad-shooter built in Python with [Kivy](https://kivy.org). Steer a running squad, pass through gates to multiply your numbers, mow down enemy waves with the crowd's combined auto-fire, and topple a boss at the end of every world.

Swellfire is the second cross-platform Kivy game by Ahmed Gad, following [CoinTex](https://github.com/ahmedfgad/CoinTex). One Python codebase runs on **Windows, macOS, Linux, Android and iPhone**.

---

## ✨ What's in 1.0

- **6 worlds, 60 levels.** Meadow → Desert → Industrial → Snowfield → Volcano → Cosmos, ten levels each, every world capped by a boss fight.
- **Squad-multiplier gates.** Pass the right gate to grow the crowd (`×2`, `+5`, …) — more runners means more firepower. Rare bonus gates hand you a weapon swap or a booster charge.
- **Auto-fire combat.** Your whole squad fires at the nearest enemy. Bigger squad, denser hail.
- **4 weapons.** Pistol, Rifle, Shotgun and Sniper — each upgradeable through four tiers in the shop.
- **6 boosters.** Grenade, Shield, Reinforcements, Freeze, Overdrive and Magnet — tap to turn a losing run around.
- **Shop & coins.** Earn coins as you play, then buy and upgrade weapons, boosters and squad bonuses.
- **Star ratings.** Three stars per level to chase, and a progress bar that turns into a boss-petrify meter on boss levels.
- **Versus multiplayer.** Race a friend on a nearby device — both squads are visible on each screen, with a side-by-side results comparison.
- **Lively, animated presentation.** Particle pops, screen shake, sprite flashes and smooth screen/modal transitions throughout — built to delight younger players.
- **Music & sound.** Per-world music beds and distinct sound cues for every action.
- **Autoplay.** A built-in genetic-algorithm autoplayer can run the game hands-free.

---

## ⬇️ Downloads

Pick your platform below. Desktop builds are ready-to-run; the mobile builds are **unsigned** (no Apple/Google account was needed to produce them), so you install them by sideloading.

| Platform | File | How to install |
|---|---|---|
| **Windows** | `Swellfire-windows.exe` | Download and run. Windows SmartScreen may warn on an unsigned app — choose "More info → Run anyway". |
| **macOS** | `Swellfire-macos.zip` | Unzip and open `Swellfire.app`. First launch: right-click → Open to bypass Gatekeeper. |
| **Linux** | `Swellfire-linux` | `chmod +x Swellfire-linux` then run it. Single self-contained file. |
| **Android** | `Swellfire-android.apk` | Unsigned **debug** build for sideloading. Enable "install unknown apps" for your browser/file manager, then open the APK. |
| **iPhone** | `Swellfire-unsigned.ipa` | Sideload with [AltStore](https://altstore.io) or Sideloadly — they re-sign it with your own Apple ID. See `IOS_INSTALL.md`. |
| **iPhone (Xcode)** | `Swellfire-xcode-project.zip` | Prefer to build it yourself? Open the project on a Mac, set your team, Archive, and run on your device or upload to the App Store. |

> The signed Google Play `.aab` is **not** attached here — it requires the private upload keystore and is produced separately with `./build_android.sh`.

---

## 🎮 How to play

- The hero runs forward automatically — you only steer. **Drag left/right** to move, release to coast.
- Gates come in pairs. **Steer through the one you want** — its effect applies to your whole squad.
- Enemy waves stream toward you; your squad auto-fires. **Runners are lost on contact** with enemies and hazards.
- Reach each world's **boss** with as big a squad as you can, and spend booster charges to swing the fight.

---

## 🛠️ Run from source

Requires Python 3.12 (developed against Kivy 2.3.1):

```bash
git clone https://github.com/ahmedfgad/Swellfire.git
cd Swellfire
python -m pip install -r requirements.txt
python main.py
```

On a machine with no audio output, start with `SDL_AUDIODRIVER=dummy python main.py`.

---

## 📝 Notes

- **Unsigned mobile builds.** The Android `.apk` and iOS `.ipa` here are unsigned by design so they can be built without any developer account. They are intended for sideloading/testing, not store distribution.
- **Build it yourself.** Every artifact above is reproducible: `./build_desktop.sh` (Windows/macOS/Linux), `./build_android.sh` (Android, signed release), and the iOS GitHub Actions workflow. Tagging a `v*` release builds and publishes all platforms automatically.

---

*Made with Python + Kivy by Ahmed Gad.*
