# Store metadata and assets

This is the index for Swellfire's public store information. Platform-specific
copy lives in the files below so field limits and review notes do not get mixed
together.

| Store | Listing source | Release guide |
| --- | --- | --- |
| Google Play | `android/google-play-metadata.md` | `README.md` — Android release build |
| Apple App Store | `ios/app-store-metadata.md` | `docs/release/app-store.md` |

## Shared identity

| Field | Value |
| --- | --- |
| Public name | Swellfire |
| Android package | `com.vilvik.swellfire` |
| Apple bundle ID | `com.vilvik.swellfire` |
| Current version | `1.0.2` |
| Developer | Ahmed Fawzy Gad |
| Support email | `ahmed.f.gad@gmail.com` |
| Support page | `SUPPORT.md` |
| Privacy policy | `PRIVACY.md` |
| Business model | Free; no ads or in-app purchases |
| Languages | English only |

## Store media

| Asset | Location |
| --- | --- |
| App icon | `icon.png` |
| Google Play feature graphic | `marketing/feature_graphic_1024x500.png` |
| Google Play phone screenshots | `marketing/01_menu.png` through `08_guide.png` |
| Google Play tablet screenshots | `marketing/tablet_screenshots/` |
| App Store iPhone screenshots | `marketing/app_store/iphone_6_9/` |
| App Store iPad screenshots | `marketing/app_store/ipad_13/` |

Before each release, keep the version in both listing files aligned with
`buildozer.spec` and `ios/app.env`, review privacy and content declarations,
verify every image visually, and update the release notes. Store credentials,
signing keys, certificates, and provisioning profiles do not belong in these
documents or in Git.
