# Android signing notes

Swellfire is signed for Google Play with an upload key. This document describes the keystore the build script creates, how Play App Signing fits in, and what to do if you ever lose the upload key.

## Day-one setup (one time)

The first time you run `./build_android.sh`, it creates everything signing needs:

```
./build_android.sh
```

After the first run, the working tree contains:

- `swellfire-upload.keystore` — the PKCS12 keystore with the upload key.
- `.env` — the keystore password and alias, used by the build script. Mode `0600`.
- `upload_certificate.pem` — the public certificate matching the upload key. Submit this to Play Console when enrolling in Play App Signing.

All three are listed in `.gitignore` and must never be committed. Back them up to a safe place (a password manager or an encrypted drive) right after the first build.

## Enrolling in Play App Signing (strongly recommended)

When you create the Swellfire app in Play Console for the first time, **enable Play App Signing** during the initial release flow. Google then holds the real signing key and you only need to protect the upload key. If the upload key is ever lost, Google can reset it — the app on Play stays signed by the same (Google-held) key, so existing users keep getting updates as normal.

If Play App Signing is disabled (you sign the app yourself with the upload key), and the upload key is lost, the app cannot be updated by anyone, ever. The only option is to publish a fresh app under a new package id and ask users to install the new one. This is the case `coin.tex.cointexreactfast` was rescued from — do not repeat it. Enroll in Play App Signing from the first release.

## If the upload key is lost (Play App Signing on)

1. Run `./build_android.sh` once. It creates a new `swellfire-upload.keystore` and `upload_certificate.pem`.
2. In Play Console, open **Test and release > Setup > App integrity**, find the upload key section, and choose to reset the upload key. If the option is not visible, use **Help > Contact support** and ask to reset the upload key.
3. Upload `upload_certificate.pem`.
4. Wait for Google to apply the change (typically a day or two).
5. From then on every upload is signed with the new key. The `.aab` in `bin/` builds with it automatically. The app on Play keeps the same Google-held signing key, so existing users keep getting updates.

## If the upload key is lost (Play App Signing off)

You cannot recover. Publish a new app with a new package id:

1. Change the id in `buildozer.spec`, for example:

   ```
   package.name = swellfire2
   package.domain = com.ahmedgad
   ```

   This gives the id `com.ahmedgad.swellfire2`.

2. Build with a new keystore (the build script makes one) and turn on Play App Signing for the new app during its first release, so this cannot happen again.

3. Create a new store listing. The old listing stays up but cannot be updated.

## Keep your keys safe

The two private files created by the build script are both ignored by git:

- `swellfire-upload.keystore` — the upload key.
- `.env` — the keystore password and alias.

Back up both in a safe place (a password manager or an encrypted drive). Do not commit them.
