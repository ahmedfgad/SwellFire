# Swellfire release records and recovery checklist

Keep this document in the project and keep all private credentials in an
encrypted password manager or encrypted backup. Do not put secrets, private
keys, certificates, or keystores in Git.

## Permanent identifiers

| Platform | Identifier | Account detail |
| --- | --- | --- |
| Apple | `com.vilvik.swellfire` | Apple Developer team `Y4Q9DBXM59` |
| App Store Connect | App Apple ID `6821999904`; SKU `SWELLFIRE-IOS-1` | App name `Swellfire`; English (U.S.) |
| Google Play | Existing package ID in `buildozer.spec` | Upload certificate SHA-256 is recorded in `docs/platforms/android-signing.md` |

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

Restore `swellfire-upload.keystore`, `.env`, and `upload_certificate.pem` from
the encrypted backup as described in `docs/platforms/android-signing.md`. The
release script checks the established upload-certificate fingerprint and will
not silently create a replacement key. Never commit these files.

## Account and release gates

- Apple age ratings and the privacy label are prepared. The privacy label is
  saved as a draft; publishing it requires the account holder's accuracy/legal
  attestation. App Store Connect still needs the account's EU trader-status
  information and applicable agreements, tax, banking, content rights,
  encryption, pricing, and availability declarations.
- App Store screenshot files are prepared in the required iPhone and iPad
  sizes; they still need uploading to the App Store Connect media slots.
- App Review contact name and email are filled from the existing Apple app
  listing. App Store Connect still requires the review contact phone number.
- Apple signing materials are not currently present in GitHub Actions, so a
  signed iOS archive cannot yet be produced by the workflow.
- The Android production signing files are not in the repository checkout. A
  release AAB cannot be built or published until they are restored.
- Keep the original signing material and recovery instructions backed up before
  making future releases.
