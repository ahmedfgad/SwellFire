# Android signing notes

Swellfire has an established Google Play upload key. Its certificate SHA-256
fingerprint is:

`564b9f2769f6bd80eda784cb29886cc28f0375531d653718e4c3e52f7c889b96`

`scripts/build_android.sh` verifies this fingerprint before every release build and
stops if a different key is present. It never creates a replacement key
automatically. Debug builds do not use the production key.

## Restore the signing files

Restore these files from the secure backup before building a release:

- `swellfire-upload.keystore` — the PKCS12 keystore containing the upload key;
- `.env` — the keystore password and alias, with file mode `0600`; and
- `upload_certificate.pem` — the matching public certificate.

All three are ignored by Git and must never be committed. With the files in the
repository root, run:

```
./scripts/build_android.sh
```

The script checks both the keystore and, when present, the PEM certificate
before invoking Buildozer.

## Play App Signing

Keep Play App Signing enabled. Google then protects the app-signing key while
this repository uses the separate upload key. If the upload key is lost, Google
can approve a reset without changing the key used to deliver updates to users.

If Play App Signing is disabled and the production signing key is lost, the
existing package cannot be updated. A new package ID and store listing would be
required.

## If an upload-key reset is required

1. Create a replacement upload keystore deliberately and export its public
   certificate. Do not change the expected fingerprint in `scripts/build_android.sh`
   yet.
2. In Play Console, open **Test and release > Setup > App integrity** and request
   an upload-key reset. If the option is unavailable, contact Play support.
3. Submit the replacement public certificate and wait for confirmation.
4. Only after Google accepts it, update the expected fingerprint, `.env`,
   keystore, and PEM together.
5. Build again and verify the APK certificate before publishing.

Keep the keystore and `.env` in a password manager or encrypted backup. Store
the PEM alongside them as a convenient public reference.
