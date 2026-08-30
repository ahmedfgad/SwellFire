# App Store Connect metadata draft

Use this as the source of truth when creating the first App Store Connect
record. Review every field against the final archive before submitting.

| Field | Value |
| --- | --- |
| Name | Swellfire |
| Subtitle | Grow your squad. Open fire. |
| Bundle ID | `com.vilvik.swellfire` |
| SKU | `SWELLFIRE-IOS-1` |
| Primary language | English (U.S.) |
| Primary category | Games — Action |
| Secondary category | Games — Casual |
| Version | `1.0.1` |
| Copyright | 2026 Ahmed Fawzy Gad |
| Support URL | `https://github.com/ahmedfgad/SwellFire/blob/main/SUPPORT.md` |
| Privacy policy URL | `https://github.com/ahmedfgad/SwellFire/blob/main/PRIVACY.md` |

## Promotional text

Grow a tiny squad into a wall of fire. Pick the best gates, upgrade four
weapons, use six boosters, and fight through 60 levels and six boss worlds.

## Description

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

## Keywords

`runner,shooter,squad,arcade,action,gates,offline,autoplay,multiplayer,boss,casual`

## App review notes

No login or review credentials are required. All solo content works without
Local Network permission. To exercise multiplayer, open Multiplayer, choose
Host on one device and Join on another reachable device, then enter the host's
displayed IP address. The Local Network purpose string explains this use.

The app uses standard HTTPS/TLS only and declares
`ITSAppUsesNonExemptEncryption = false`. Confirm the export-compliance answers
in App Store Connect against the final binary.

## Privacy questionnaire draft

Answer **Yes, data is collected**, then declare **Other Data** used only for
**App Functionality**, **not linked to the user**, and **not used for tracking**.
This conservative disclosure covers the internet-facing IP address received by
the public-address provider when the user opens the Host screen. There is no
developer-operated server, account, analytics, advertising, or tracking.

Reconfirm the providers' behavior immediately before submission. The answers
must include all third-party practices and must match `PRIVACY.md` and the
privacy manifest in the archived app.

## Age rating answers to review

The game contains stylized shooting and enemy defeat but no realistic gore,
gambling, sexual content, drugs, profanity, user-generated content, or open web
browsing. Answer Apple's current questionnaire truthfully; Apple calculates the
regional rating, so do not enter a guessed numeric rating from this document.

## Required media

Generate and visually review the eight screenshots for both checked-in device
families:

```bash
python -m pip install -r requirements/media.txt
python tools/make_app_store_screenshots.py
```

Upload from:

- `marketing/app_store/iphone_6_9/` — 1284×2778 portrait;
- `marketing/app_store/ipad_13/` — 2064×2752 portrait.

App Store icons are generated into the Xcode asset catalog during the build,
including the alpha-free 1024×1024 marketing icon.
