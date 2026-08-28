# Google Play listing

Use this file when updating the English (United States) main store listing.
Keep the live listing in Play Console unchanged where it contains verified
account or contact details that are not stored in this repository.

| Field | Value |
| --- | --- |
| App name | Swellfire |
| Package name | `com.vilvik.swellfire` |
| App or game | Game |
| Category | Action |
| Default language | English (United States) |
| Price | Free |
| Contains ads | No |
| In-app purchases | No |
| Version name | `1.0.1` |
| Version code | `10001` |
| Contact email | `ahmed.f.gad@gmail.com` |
| Support URL | `https://github.com/ahmedfgad/SwellFire/blob/main/SUPPORT.md` |
| Privacy policy URL | `https://github.com/ahmedfgad/SwellFire/blob/main/PRIVACY.md` |

Google currently limits the app name to 30 characters, the short description
to 80, and the full description to 4,000. The text below stays within those
limits. Recheck the limits in [Play Console Help](https://support.google.com/googleplay/android-developer/answer/9859152)
before changing the listing.

## Short description

Swell your squad, choose the best gates, and battle through six worlds.

## Full description

Swellfire is a portrait auto-runner squad shooter. Steer left and right while
your squad fires automatically, choose gates that multiply your runners, clear
enemy waves, and defeat the boss at the end of each world.

Play through 60 levels across six themed worlds. Earn coins and stars, upgrade
Pistol, Rifle, Shotgun, and Sniper weapons, and turn difficult runs around with
Grenade, Shield, Reinforcements, Freeze, Overdrive, and Magnet boosters.

Features:

- six worlds and 60 levels;
- squad-multiplying gates and auto-fire combat;
- four upgradeable weapons and six boosters;
- boss fights, star ratings, and saved progress;
- an optional genetic-algorithm Auto Player; and
- optional direct two-player multiplayer over a reachable network.

No account, advertisements, tracking, or in-app purchases.

## What's new in 1.0.1

- Updated for Android 16 and API level 36.
- Improved edge-to-edge spacing and larger touch controls.
- Improved pause, resume, Back button, and audio behavior.
- Hardened saved progress, purchases, boosters, and multiplayer messages.
- Fixed delayed dialogs and multiplayer connection cleanup.

## Graphics

| Play Console slot | Repository asset |
| --- | --- |
| 512×512 app icon | `icon.png` |
| 1024×500 feature graphic | `swellfire_media/feature_graphic_1024x500.png` |
| Phone screenshots, eight | `swellfire_media/01_menu.png` through `08_guide.png` |
| 10-inch tablet screenshots, eight | `swellfire_media/tablet_screenshots/` |
| Optional preview video | Use the published promo-video URL, not a local file path |

The feature graphic is a 24-bit, alpha-free PNG. Google accepts up to eight
screenshots per supported device type and requires a 1024×500 feature graphic.
The current rules and accessibility guidance are in
[Google's preview-asset documentation](https://support.google.com/googleplay/android-developer/answer/9866151).

Suggested screenshot alt text, in upload order:

1. Swellfire main menu with Play, Shop, Multiplayer, Guide, and Settings.
2. Six-world selection screen with Meadow ready to play.
3. Meadow roadmap showing ten levels and the first level selected.
4. A growing squad choosing between two gates while firing at enemies.
5. The squad firing at the Meadow world boss.
6. Level-complete dialog showing stars, score, and next-level controls.
7. Shop showing upgradeable weapons and gameplay boosters.
8. Game guide explaining steering, gates, enemies, coins, and boosters.

## App content declarations

Review these answers in Play Console whenever the app or its dependencies
change:

- App access: all solo content is available without a login. Multiplayer needs
  two reachable devices but is not required to review the game.
- Ads: no.
- Target audience: the game is not specifically designed for children. The
  recommended selected groups are 13–15, 16–17, and 18 and over. Confirm this
  still describes the intended audience before submission.
- Content rating: disclose stylized shooting and enemy defeat. There is no
  realistic gore, gambling, sexual content, drugs, profanity, user-generated
  content, or unrestricted web access. Submit the questionnaire and use the
  ratings assigned by IARC rather than entering a guessed rating.
- News apps, health apps, financial features, government affiliation, ads, and
  in-app purchases: not applicable.

Every published app needs a completed Data safety form, even when most data
stays on the device. Saved progress and settings are local and are not sent to
the developer. Optional direct multiplayer sends game messages only between
the two player-supplied addresses. Opening the Host screen contacts
`api.ipify.org`, `ifconfig.me`, or `icanhazip.com` over HTTPS; those providers
necessarily receive the connecting IP address and may keep operational logs.

Do not answer “no data collected” without accounting for those public-address
providers. Follow [Google's current IP-address guidance](https://support.google.com/googleplay/android-developer/answer/10787469),
review the providers' policies, and disclose the applicable category as
optional App Functionality, encrypted in transit, not used for advertising or
tracking, and retained only as the provider actually documents. Keep the final
answers consistent with `PRIVACY.md`.

## Production upload

Upload the signed Android App Bundle for version `1.0.1` (`10001`) to the
production release in Play Console. Keep the signed APK for direct downloads
and the GitHub release. Before rollout, confirm that Play App Signing accepts
the active upload certificate and that `10001` is higher than the version code
already published.
