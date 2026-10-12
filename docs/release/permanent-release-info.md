# Swellfire release records and recovery checklist

Keep this document in the project and keep all private credentials in an
encrypted password manager or encrypted backup. Do not put secrets, private
keys, certificates, or keystores in Git.

## Permanent identifiers

| Platform | Identifier | Account detail |
| --- | --- | --- |
| Apple | `com.vilvik.swellfire` | Apple Developer team `Y4Q9DBXM59` |
| App Store Connect | App Apple ID `6821999904`; SKU `SWELLFIRE-IOS-1` | App name `Swellfire`; English (U.S.) |
| Google Play | `com.vilvik.swellfire`; Play app ID `4975235522428198839` | Personal developer account `4818949690814466544`; upload certificate SHA-256 is recorded in `docs/platforms/android-signing.md` |

The iOS marketing version and build number live in `ios/app.env`. Bump the
build number for every uploaded App Store build. Keep the listing text in
`ios/app-store-metadata.md`, Android listing text in
`android/google-play-metadata.md`, and screenshots in `marketing/`.
The App Store Connect draft is configured as a free public app in all 175
countries or regions, matching the free Google Play listing. Availability takes
effect only when the app is released. France remains selected, so complete the
French encryption declaration before submitting the version for review.

## Apple signing recovery

The shared Apple signing backup is in the owner's encrypted OneDrive folder
`Secrets\apple-signing`. It contains the team distribution certificate and
private key, App Store Connect API key, issuer/key identifiers, and the
Swellfire-specific profile at `Swellfire Profile\Swellfire_Provisioning_Profile.mobileprovision`.
The P12 was re-encrypted on 2026-10-12 with a fresh password; `Info.txt` in
that folder now has the updated password. The Apple certificate itself was not
replaced or revoked. Keep this folder backed up in the password manager or a
second encrypted archive.

These workflow values are configured as encrypted GitHub Actions secrets:

| GitHub Actions secret | Secure backup item |
| --- | --- |
| `APPLE_TEAM_ID` | Apple Developer team ID (`Y4Q9DBXM59`; identifier, not secret) |
| `APPLE_DISTRIBUTION_CERTIFICATE_BASE64` | Base64 of the Apple Distribution `.p12` export |
| `APPLE_DISTRIBUTION_CERTIFICATE_PASSWORD` | Password for the `.p12` export |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Base64 of the App Store provisioning profile for `com.vilvik.swellfire` |
| `APPLE_API_KEY_BASE64` | Base64 of the team's App Store Connect API `.p8` key |
| `APPLE_API_KEY_ID` | App Store Connect API key identifier |
| `APPLE_API_ISSUER_ID` | App Store Connect API issuer identifier |

Keep the `.p12`, its password, API key, and provisioning profile together in the
encrypted backup. The **Archive iOS for App Store** workflow signs and validates
the build, preserves a private workflow artifact, and uploads the IPA to App
Store Connect for processing. It does not submit the app for review or release it.

## Android signing recovery

The verified signing backup is stored in the owner's encrypted OneDrive folder
`SwellFire Play Console Upload Key`. It contains `swellfire-upload.keystore`,
`.env`, and `upload_certificate.pem`. Keep that backup and a second encrypted
password-manager/backup copy for future releases; never commit these files.

The matching key, password, and alias are configured as GitHub Actions
repository secrets: `SWELLFIRE_UPLOAD_KEYSTORE_BASE64`,
`SWELLFIRE_UPLOAD_KEYSTORE_PASSWORD`, and
`SWELLFIRE_UPLOAD_KEYSTORE_ALIAS`. The one-time **Build signed Google Play
bundle** workflow verifies the upload certificate before creating an AAB and
keeps the build as a short-lived Actions artifact. Download the artifact and
upload it in Play Console. The local release script also checks the known
fingerprint and refuses to silently create a replacement key. Details are in
`docs/platforms/android-signing.md`.

## Account and release gates

- The App Privacy label is published with the account holder's confirmed
  answers: Other Data linked to the user, used for app functionality, and not
  used for tracking. Revisit it if data practices or provider behavior change.
- The account holder confirmed non-trader status while choosing EU distribution;
  Apple's Digital Services Act compliance shows Active for all 27 EU regions.
- The account holder confirmed the background soundfont is their own work.
  App Store Connect content rights are set to no third-party content; revisit
  this declaration if third-party content is added.
- The free Apps Agreement is active. Paid Apps Agreement is not needed unless
  the app later adds paid distribution or in-app purchases.
- The iOS app uses OpenSSL-backed TLS for its optional public-IP lookup. Its
  Info.plist declares non-exempt encryption, and the build must receive Apple's
  export-compliance determination before App Review.
- Because France is selected and TLS uses standard encryption outside Apple's
  operating system, Apple requires a French encryption declaration in App
  Store Connect. ANSSI's official filing is at
  <https://demarche.numerique.gouv.fr/commencer/declaration-relative-a-un-moyen-de-cryptologie>.
  The current process requires an authenticated applicant and supporting
  organization and product materials. The account holder must complete the
  authenticated declaration and its legal attestation; it has not been filed.
- Eight screenshots for the current iPhone Dynamic Island medium slot and eight
  for the iPad 13-inch slot are uploaded in App Store Connect. Their source
  images remain under `marketing/app_store/`.
- App Review contact details are saved in App Store Connect, including the
  phone number supplied by the account holder.
- The App Privacy label is published with the account holder's confirmed
  answers: Other Data linked to the user, used for app functionality, and not
  used for tracking. It should be revisited if data practices or provider
  behavior changes.
- The account holder confirmed non-trader status while choosing EU distribution;
  Apple's Digital Services Act compliance shows Active for all 27 EU regions.
- The account holder confirmed the background soundfont is their own work.
  App Store Connect content rights are set to no third-party content; revisit
  this declaration if third-party content is added.
- Apple signing materials are configured in GitHub Actions. Swellfire uses the
  existing team distribution certificate and API key shared with CoinTex, and
  its own App Store profile. Do not create a duplicate team certificate or API
  key. The CoinTex session has created its separate app profile.
- The Android upload key is verified and stored in the encrypted backup and
  GitHub Actions secrets. Google Play rejected the first signed AAB because
  automatic protection requires minimum API 24; the app configuration now
  targets API 24 and the replacement release uses version code 10004. This
  drops support for Android 5.0–6.x while that Play protection remains enabled.
  The rejected upload was removed from the production release draft; upload the
  rebuilt 10004 bundle before rollout.
- Keep the original signing material and recovery instructions backed up before
  making future releases.
