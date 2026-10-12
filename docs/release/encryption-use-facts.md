# Swellfire encryption use: technical facts

Prepared for the account holder's export-compliance review. This records
implementation details; it is not a legal classification or government filing.

## iOS implementation

- The app includes CPython and uses its standard-library `ssl` and
  `urllib.request` modules for an optional public-IP lookup when the Host screen
  opens.
- The request uses HTTPS to one of the configured public-IP endpoints. TLS
  certificate verification is enabled; the app does not fall back to an
  unverified request.
- The iOS Python runtime is built with the `kivy-ios` toolchain and its
  OpenSSL-backed Python SSL module. This TLS implementation is outside Apple's
  operating-system TLS APIs.
- The lookup is optional and does not transmit account credentials. If it
  fails, the app allows the user to enter/share an address manually.
- Two-player game traffic uses direct TCP sockets and length-prefixed JSON on
  the selected network; this game protocol does not add TLS encryption.

## Source references

- `swellfire/net.py`: `PUBLIC_IP_SERVICES`, `_ssl_contexts()`, and
  `get_public_ip()` implement the HTTPS lookup; `NetHost` and `NetClient`
  implement direct TCP gameplay.
- `requirements/ios.txt`: selects the `kivy-ios` build toolchain.
- `tools/ios_configure_project.py`: writes
  `ITSAppUsesNonExemptEncryption = true` into the iOS app plist.

## Filing status

App Store Connect requires its export-compliance determination. Because the
listing includes France and the app uses standard TLS outside Apple's OS,
Apple's documentation says a French encryption declaration is required.
ANSSI's authenticated filing and required organization/product attachments
remain for the account holder to complete. See
[`permanent-release-info.md`](permanent-release-info.md).
