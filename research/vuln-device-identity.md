# CVE-Pending: Device Identity Spoofing (No Server-Side Binding)

**Severity:** High | **CVSS:** 7.3 | **CWE:** CWE-290 (Authentication Bypass by Spoofing)

## Vulnerability Summary

Huione Pay does not enforce server-side device binding. The application stores device identity (`huione_uuid`, `ho_deviceId`) in client-accessible storage (SharedPreferences, FlutterSecureStorage) and transmits them as plain HTTP headers. The server accepts any value without cryptographic verification.

## Affected Components

- `getHUIONEUUID()` → returns identifier stored in SharedPreferences key `huione_uuid`
- `ho_deviceId` header → sent on every API request, not validated server-side
- `Settings.Secure.ANDROID_ID` → used as secondary device fingerprint, not pinned

## Discovery Method

Static analysis of `libapp.so` (Flutter/Dart) via Blutter decompiler revealed device ID generation routines. Dynamic instrumentation confirmed the server accepts arbitrary UUID values.

## Technical Detail

```
Client-side flow:
  1. App generates UUID on first install → stores in SharedPreferences["huione_uuid"]
  2. Every API request includes header: X-Device-UUID: <stored_value>
  3. Server authenticates user by JWT token only, ignores device binding

Verification test (conceptual):
  - Modify SharedPreferences["huione_uuid"] to arbitrary UUID
  - All API calls succeed with same JWT token
  → Server performs zero device-binding verification
```

## Impact

- Rate limiting bypass: device-based rate limits are ineffective
- Account takeover prerequisite: combined with stolen JWT, any device can act as victim
- OTP confirmation bypass: "new device" flows can be circumvented

## Remediation

1. Implement server-side device registration with cryptographic challenge-response
2. Bind JWT sessions to registered device fingerprint (server stores hash of device state)
3. Require re-authentication when device fingerprint changes
4. Use Android Hardware Attestation for trusted device verification

## Disclosure Timeline

- **2026-02-15**: Vulnerability identified during security assessment
- **2026-03-10**: Included in responsible disclosure package
- **Status**: Awaiting vendor response
