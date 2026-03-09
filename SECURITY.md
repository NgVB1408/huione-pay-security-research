# Security Policy & Responsible Disclosure

## Reporting New Vulnerabilities

If you discover additional vulnerabilities in Huione Pay or related infrastructure, please follow responsible disclosure:

1. **Do NOT** publish vulnerability details publicly before notifying the vendor
2. **Contact** the research team at: security-research@proton.me
3. **Include** sufficient technical detail for reproduction
4. **Allow** 90 days for vendor response before public disclosure

---

## Disclosure Timeline — Huione Pay Research

| Date | Event |
|------|-------|
| 2025-Q4 | Initial research began — static analysis of APK |
| 2025-Q4 | Frida Gadget instrumentation deployed on test device |
| 2026-01 | SSL pinning bypass achieved — traffic analysis begun |
| 2026-01 | AES key extraction confirmed (`keyhead_project_xhui_one_keytail`) |
| 2026-02 | Full 18-vulnerability report compiled |
| 2026-02 | Infrastructure evidence captured (timestamped JSON) |
| 2026-02 | Blockchain C2 infrastructure identified on BSC |
| 2026-03 | HackerOne/Bugcrowd submissions prepared |
| 2026-03 | Chainalysis intelligence team notification |
| 2026-03 | FinCEN cybercrime report filed |
| 2026-03 | **Public disclosure** (this repository) |

---

## Scope of Research

### In Scope
- `com.huione.pay` Android application (all versions)
- `app.hh3721.com` API infrastructure
- `rpc.huione.org` blockchain RPC
- BSC smart contract `0xe9d5f645f79fa60fca82b4e1d35832e43370feb0`
- S3 configuration at `datadogips.s3.ap-southeast-1.amazonaws.com`
- MQTT broker `wss-mqtt.xone.la`

### Out of Scope
- Other Huione Group products not analyzed
- Third-party services used by the application
- Social engineering attacks

---

## Research Ethics Statement

This security research was conducted with the following ethical principles:

1. **No unauthorized access** to production user accounts
2. **No data exfiltration** — all testing on isolated environment
3. **No financial harm** — no actual funds transferred or manipulated
4. **Minimal footprint** — testing limited to own test account
5. **Documentation first** — all findings documented before any disclosure

---

## CVE Assignments

CVE assignments pending for the following critical findings:

| Vulnerability | Severity | CVE Status |
|--------------|----------|-----------|
| Hardcoded AES-256 key | Critical | Pending |
| IDOR account manipulation | Critical | Pending |
| OTP bypass | Critical | Pending |
| Withdrawal address manipulation | Critical | Pending |
| Multi-signature race condition | Critical | Pending |

---

## Contact Information

- **Primary:** security-research@proton.me
- **Secondary:** Submit via HackerOne private program
- **PGP Fingerprint:** Available upon request
- **Response SLA:** 48 hours for initial acknowledgment
