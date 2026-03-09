# Responsible Disclosure Email Templates

---

## Template A — Vendor Notification (Huione Pay)

```
To: security@huione.com / support@huione.com
Subject: [SECURITY] Critical Vulnerabilities in Huione Pay Android Application

Dear Huione Pay Security Team,

I am an independent security researcher who has conducted a security 
assessment of the Huione Pay Android application (com.huione.pay).

I have identified 18 vulnerabilities, including several of Critical severity
that could result in complete account compromise and financial theft for 
your users.

Key findings:
- Hardcoded AES-256 encryption key in libapp.so (CVSS 9.8)
- IDOR on transfer endpoint allowing cross-account transactions (CVSS 9.1)
- OTP bypass via missing rate limiting (CVSS 9.3)
- SSL pinning bypassable via Frida instrumentation (CVSS 8.8)
- 4-layer encryption fully breachable (CVSS 9.8)

I am following responsible disclosure principles and am prepared to:
1. Provide full technical details under NDA if required
2. Allow 90 days for remediation before public disclosure
3. Verify fixes before public release of PoC code

Please respond within 7 days to establish a disclosure timeline.

Full report: [link or attachment]

Regards,
Independent Security Researcher
security-research@proton.me
```

---

## Template B — Chainalysis Intelligence

```
To: intelligence@chainalysis.com
Subject: Threat Intelligence: Blockchain C2 Infrastructure — Huione Pay (BSC)

Dear Chainalysis Intelligence Team,

I am sharing threat intelligence regarding a BSC smart contract cluster
associated with the Huione Pay mobile application, which has been linked
to financial crime facilitation in Southeast Asia.

Key on-chain indicators:
- C2 contract: 0xe9d5f645f79fa60fca82b4e1d35832e43370feb0 (BSC)
- C2 owner:    0x849008a657e7b48e993d8ffd5c7ad29c95598905
- Mix contract: 0x000037bb05b2cef17c6469f4bcdb198826ce0000 (~$31,800 BNB)
- C2 URL (on-chain): https://8kwfaa30jtlnwi.com

The Mid Contract implements a bulkWithdraw(uint256[], address[]) function
consistent with on-chain mixing activity.

Full technical report and infrastructure evidence attached.

Regards,
Independent Security Researcher
security-research@proton.me
```

---

## Template C — CISA Vulnerability Coordination

```
To: coordinated-vulnerability-disclosure@cisa.dhs.gov
Subject: Voluntary CVD Submission — Huione Pay Financial Application

I am submitting this report under CISA's Coordinated Vulnerability Disclosure
program regarding critical security vulnerabilities in the Huione Pay 
financial application.

The application serves users in multiple jurisdictions and contains 
vulnerabilities that could enable large-scale financial fraud.

Attached: Full vulnerability report (18 findings, CVSS 6.5–9.8)

Requesting CERT/CC coordination for CVE assignment and vendor notification.
```
