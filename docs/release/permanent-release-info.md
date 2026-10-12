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
effect only when the app is released.

## Apple signing recovery

Back up these items in the password manager or encrypted archive and add the
workflow values to GitHub Actions before running **Archive iOS for App Store**:

| GitHub Actions secret | Secure backup item |
| --- | --- |
| `APPLE_TEAM_ID` | Apple Developer team ID (`Y4Q9DBXM59`; identifier, not secret) |
| `APPLE_DISTRIBUTION_CERTIFICATE_BASE64` | Base64 of the Apple Distribution `.p12` export |
| `APPLE_DISTRIBUTION_CERTIFICATE_PASSWORD` | Password for the `.p12` export |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Base64 of the App Store provisioning profile for `com.vilvik.swellfire` |

Keep the original `.p12`, its password, and the provisioning profile together
in the encrypted backup. The current workflow creates and validates the signed
IPA but does not upload it to Apple. App Store Connect API credentials are not
currently configured or required by that workflow.

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

- Apple age ratings and the privacy label are prepared. The privacy label is
  saved as a draft; publishing it requires the account holder's accuracy/legal
  attestation. App Store Connect still needs the account's EU trader-status
  information and applicable agreements, tax, banking, content rights,
  encryption, pricing, and availability declarations.
- Eight screenshots for the current iPhone Dynamic Island medium slot and eight
  for the iPad 13-inch slot are uploaded in App Store Connect. Their source
  images remain under `marketing/app_store/`.
- App Review contact details are saved in App Store Connect, including the
  phone number supplied by the account holder.
- The privacy label is saved as a draft. The account holder confirmed its data
  answers, but Apple still asks for an action-time confirmation to publish the
  label.
- Apple signing materials are not currently present in GitHub Actions. The
  CoinTex release uses the same Apple team and is coordinating creation of a
  team-wide distribution certificate/API key before SwellFire configures its
  app-specific provisioning profile and secrets.
- The Android upload key is verified and stored in the encrypted backup and
  GitHub Actions secrets. The signed release workflow is ready; its AAB still
  needs to be built and uploaded to Play Console.
- Keep the original signing material and recovery instructions backed up before
  making future releases.
