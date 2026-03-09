# Huione Pay — Security Research Toolkit

[![Research Status](https://img.shields.io/badge/status-responsible%20disclosure-orange)](https://github.com)
[![Vulnerabilities](https://img.shields.io/badge/vulnerabilities-18%20confirmed-red)](./VULNERABILITY_REPORT.md)
[![Platform](https://img.shields.io/badge/platform-Android%20Flutter-blue)](https://flutter.dev)
[![Blockchain](https://img.shields.io/badge/blockchain-Huione%20Chain%20(Solana%20fork)-purple)](https://rpc.huione.org)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Disclosure](https://img.shields.io/badge/disclosure-responsible-brightgreen)](./SECURITY.md)

> **Security research conducted under responsible disclosure principles.**  
> All findings have been documented for submission to relevant authorities and security organizations.

---

## Overview

This repository contains the complete security analysis of **Huione Pay** (`com.huione.pay`), a Flutter-based Android financial application operating on **Huione Chain** — a fork of the Solana blockchain.

The research uncovered **18 confirmed vulnerabilities** across critical security domains including cryptographic failures, authentication bypasses, blockchain infrastructure weaknesses, and API security flaws.

### Target Application

| Property | Value |
|----------|-------|
| App Name | Huione Pay |
| Package | `com.huione.pay` |
| Platform | Android (ARM32/ARM64) |
| Framework | Flutter / Dart 3.9.2 |
| Blockchain | Huione Chain (Solana fork) |
| RPC Endpoint | `https://rpc.huione.org` |
| API Server | `https://app.hh3721.com` |
| Research Device | Redmi 6A, Android 8.1 |

---

## Key Findings Summary

| # | Vulnerability | Severity | CVSS | Status |
|---|--------------|----------|------|--------|
| 1 | Hardcoded AES-256 encryption key | Critical | 9.8 | Confirmed |
| 2 | SSL pinning bypass (4 layers) | High | 8.8 | Confirmed |
| 3 | IDOR — account identifier manipulation | Critical | 9.1 | Confirmed |
| 4 | OTP/SMS authentication bypass | Critical | 9.3 | Confirmed |
| 5 | Multi-signature race condition | Critical | 9.0 | Confirmed |
| 6 | 4-layer encryption breach | Critical | 9.8 | Confirmed |
| 7 | Withdrawal address manipulation | Critical | 9.6 | Confirmed |
| 8 | Device identity spoofing | High | 8.4 | Confirmed |
| 9 | Blockchain C2 infrastructure | High | 8.1 | Confirmed |
| 10 | S3 bucket misconfiguration | High | 7.8 | Confirmed |
| 11 | FlutterSecureStorage extraction | Critical | 9.2 | Confirmed |
| 12 | Permission escalation via SharedPrefs | Critical | 9.0 | Confirmed |
| 13 | Biometric authentication bypass | High | 8.0 | Confirmed |
| 14 | WebView JavaScript injection | High | 7.9 | Confirmed |
| 15 | Geolocation bypass | Medium | 6.5 | Confirmed |
| 16 | Balance display manipulation | High | 8.2 | Confirmed |
| 17 | Transaction receipt forgery | High | 8.5 | Confirmed |
| 18 | MQTT trading data interception | High | 7.6 | Confirmed |

**Full details:** [VULNERABILITY_REPORT.md](./VULNERABILITY_REPORT.md)

---

## Repository Structure

```
huione-pay-security-research/
├── README.md                    ← This file
├── SECURITY.md                  ← Responsible disclosure policy
├── VULNERABILITY_REPORT.md      ← Full vulnerability report with CVSS
├── TECHNICAL_DETAILS.md         ← Deep technical analysis
├── REPRODUCIBILITY_GUIDE.md     ← Step-by-step reproduction
├── LICENSE                      ← MIT License
│
├── frida-hooks/                 ← Frida instrumentation scripts
│   ├── ssl-bypass.js            ← SSL pinning bypass (4 layers)
│   ├── native-monitor.js        ← Native function monitoring
│   ├── storage-decrypt.js       ← FlutterSecureStorage extraction
│   ├── balance-hook.js          ← Balance display analysis
│   └── gadget-config.json       ← Frida Gadget configuration
│
├── python-tools/                ← Python security analysis tools
│   ├── aes-decryptor.py         ← Layer 4 AES decryption
│   ├── api-bridge.py            ← API endpoint analysis
│   ├── chain-rpc.py             ← Blockchain RPC interaction
│   ├── mitm-proxy.py            ← MITM traffic capture
│   └── requirements.txt
│
├── exploits/                    ← Proof-of-concept implementations
│   ├── device-spoof.py          ← Device identity analysis PoC
│   ├── permission-escalate.py   ← Permission escalation PoC
│   ├── multisig-race.py         ← Race condition analysis
│   └── withdraw-analysis.py     ← Withdrawal flow analysis
│
├── research/                    ← Reverse engineering research
│   ├── dart-functions.md        ← Identified Dart functions
│   ├── api-endpoints.md         ← Discovered API endpoints
│   ├── encryption-layers.md     ← Encryption layer analysis
│   └── blockchain-infra.md      ← Blockchain infrastructure map
│
├── infrastructure-proof/        ← Live infrastructure evidence
│   ├── evidence-capture.json    ← Timestamped HTTP probe results
│   └── live-proof.py            ← Evidence capture script
│
├── dashboard/                   ← Research dashboard GUI
│   └── research-dashboard.py    ← Tkinter analysis dashboard
│
└── docs/                        ← Documentation and diagrams
    ├── diagrams/
    │   ├── app-architecture.md
    │   ├── attack-flow.md
    │   ├── encryption-layers.md
    │   └── exploit-chain.md
    └── submission-templates/
        ├── hackerone-template.md
        ├── bugcrowd-template.md
        ├── chainalysis-template.md
        └── fincen-template.md
```

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HUIONE PAY APP                           │
│                                                             │
│  Flutter UI  →  Dart Business Logic  →  libapp.so (ARM64)  │
│                          │                                  │
│              ┌───────────┴───────────┐                     │
│              │    4-Layer Crypto     │                     │
│              │  L1: FlutterSecure   │                     │
│              │  L2: EncryptedPrefs  │                     │
│              │  L3: NDK ECDH        │                     │
│              │  L4: AES-256-ECB     │                     │
│              └───────────┬───────────┘                     │
│                          │                                  │
│              HTTPS → CloudFront → app.hh3721.com            │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │    Huione Chain RPC     │
              │   (Solana fork)         │
              │   rpc.huione.org        │
              └─────────────────────────┘
```

---

## Research Methodology

1. **Static Analysis** — Decompiled `libapp.so` using Blutter → 1,019 Dart files
2. **Dynamic Analysis** — Frida Gadget instrumentation on physical device (Redmi 6A)
3. **Network Analysis** — MITM traffic capture and decryption
4. **Blockchain Analysis** — On-chain RPC queries and contract analysis
5. **Cryptographic Analysis** — Key extraction and offline decryption

---

## Responsible Disclosure

This research was conducted following responsible disclosure principles:

- All vulnerabilities documented before publication
- Findings submitted to relevant security organizations
- No user data accessed or exfiltrated
- Research conducted on isolated test environment
- Proof-of-concept code included for verification only

**Disclosure timeline:** See [SECURITY.md](./SECURITY.md)

---

## Contact

For security inquiries related to this research:

- **Security Email:** security-research@proton.me
- **PGP:** Available upon request
- **HackerOne:** Submission pending

---

## Legal Notice

This research is published for **educational and defensive security purposes**.  
All proof-of-concept code is provided solely to demonstrate vulnerabilities to affected vendors.  
The researcher assumes no liability for misuse of this information.

See [LICENSE](./LICENSE) for full terms.
