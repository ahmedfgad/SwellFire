# Publishing Swellfire on the Apple App Store

The App Store Connect record is created and its draft listing is initialized.
The repository is prepared for a universal iPhone/iPad App Store build. It uses
bundle ID `com.vilvik.swellfire`, version `1.0.3`, minimum iOS 15, a complete icon
catalog, a privacy manifest, verified HTTPS, and the iOS 26 SDK baseline. Signing
materials are stored outside Git and in encrypted GitHub Actions secrets.

Apple currently requires uploads to use Xcode 26 or newer with the iOS 26 SDK.
See [Apple's upcoming requirements](https://developer.apple.com/news/upcoming-requirements/).

## 1. Apple records

After the Apple Developer Program membership is active:

1. The explicit App ID `com.vilvik.swellfire` is registered under team
   `Y4Q9DBXM59`; no optional capabilities are currently required.
2. The App Store Connect app record is **Swellfire**, primary language English
   (U.S.), with SKU `SWELLFIRE-IOS-1`.
3. Complete Agreements, Tax, and Banking if required for the chosen distribution
   and price. Complete the Digital Services Act trader-status information and
   other regional compliance questions that apply to the account.
4. Use [ios/app-store-metadata.md](../../ios/app-store-metadata.md) for the listing.

The draft listing text, Games category, 13+ age rating, App Review contact and
notes, and privacy policy URL are saved in App Store Connect. Eight screenshots
are uploaded for the current iPhone Dynamic Island medium size and eight for the
iPad 13-inch size. Their source PNGs are under `marketing/app_store/`. The
privacy label is published with the account holder's confirmed answers;
revisit it if the app's data practices change. The account holder also
confirmed non-trader EU distribution status and that Swellfire contains no
third-party content; both declarations are saved in App Store Connect.

The bundle ID is the app's permanent identity. Do not use the old CI-only ID
`com.ahmedgad.swellfire`.

## 2. Validate the iOS configuration

This works on Linux or macOS and makes no network requests:

```bash
./scripts/build_ios.sh --check
```

The local configuration check verifies the app identity and Xcode project
settings. The signed release workflow runs on macOS 26 and uses Xcode 26.

## 3. Prepare signing secrets

The existing team Apple Distribution certificate and App Store Connect API key
are shared with the CoinTex release. Swellfire has its own App Store profile,
named **Swellfire App Store**, for `com.vilvik.swellfire`. The profile and
certificate are stored outside Git in the encrypted OneDrive signing folder.
The certificate container password was rotated on 2026-10-12; the certificate
and private key were not replaced. These repository secrets are configured:

| Secret | Contents |
| --- | --- |
| `APPLE_TEAM_ID` | The 10-character Apple Developer Team ID |
| `APPLE_DISTRIBUTION_CERTIFICATE_BASE64` | Base64 of the distribution `.p12` |
| `APPLE_DISTRIBUTION_CERTIFICATE_PASSWORD` | Password used when exporting the `.p12` |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Base64 of the App Store provisioning profile |
| `APPLE_API_KEY_BASE64` | Base64 of the team's App Store Connect API `.p8` key |
| `APPLE_API_KEY_ID` | App Store Connect API key ID |
| `APPLE_API_ISSUER_ID` | App Store Connect API issuer ID |

Never commit those files or values. The workflow imports them into a temporary
keychain, verifies that the profile's team and bundle ID match, and removes the
temporary signing material at the end.

## 4. Produce the signed archive

From GitHub Actions, manually run **Archive iOS for App Store** and enter a
positive build number. Every App Store Connect upload must use a new, higher
build number. The workflow:

- builds on `macos-26` and refuses an SDK older than 26;
- creates the universal iPhone/iPad Xcode project;
- embeds the privacy manifest and complete icon catalog;
- signs and validates an `.xcarchive` and App Store `.ipa`; and
- preserves those files as private workflow artifacts; and
- uploads the validated IPA to App Store Connect for build processing.

It does not submit the app for review or release it. Alternatively, on a Mac,
run `./scripts/build_ios.sh`, select the team in Xcode, and choose Product > Archive.

## 5. Test and submit

1. Wait for App Store Connect processing and resolve any validation messages.
2. Add the build to TestFlight. Test solo play, saved progress, audio, every
   screen, denied/allowed Local Network permission, host/join multiplayer, and
   a cold launch on at least one iPhone and one iPad.
3. In Xcode Organizer, generate the archive's Privacy Report and compare it with
   `ios/PrivacyInfo.xcprivacy`, `PRIVACY.md`, and the App Privacy answers.
4. Confirm the uploaded screenshots and complete any remaining metadata,
   accessibility, encryption, content-rights, pricing, and availability fields.
5. Submit for App Review. Do not release automatically until the approved build
   has passed the intended TestFlight checks.

Apple requires a privacy-policy URL and accurate disclosure of the app and its
third-party partners' data practices. See
[App privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy/).

## iPhone, iPad, and Mac availability

This target supports both iPhone and iPad. It is not a Mac Catalyst or native
macOS target. By default, a compatible iOS/iPadOS app can also be offered in the
Mac App Store on Apple-silicon Macs in an iOS compatibility window; availability
is controlled in App Store Connect and should remain enabled only after testing
mouse/trackpad input, audio, window behavior, networking, and saved data on an
Apple-silicon Mac. It will not cover Intel Macs.

The separate PyInstaller `Swellfire.app` produced by the desktop workflow is a
native desktop download, but it is currently unsigned/notarized and is not a
Mac App Store submission. Publishing a native Mac App Store edition would be a
separate signing, sandboxing, entitlement, packaging, and review project.

See Apple's documentation for
[running iOS apps on Apple-silicon Macs](https://developer.apple.com/documentation/Apple-Silicon/running-your-ios-apps-in-macos)
and [managing Mac availability](https://developer.apple.com/help/app-store-connect/manage-your-apps-availability/manage-availability-of-iphone-and-ipad-apps-on-macs-with-apple-silicon/).
