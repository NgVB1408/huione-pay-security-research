# FinCEN Cybercrime Report
# Suspicious Activity Report — Mobile Fintech Application with C2 Infrastructure

**Report Category:** Cybercrime / Suspicious Activity  
**Reporter Type:** Independent Security Researcher  
**Date:** March 2026  

---

## Subject of Report

**Application:** Huione Pay (`com.huione.pay`)  
**Operator:** Huione Group (Phnom Penh, Cambodia)  
**Platform:** Android mobile application  
**Activity Type:** Financial application with obfuscated infrastructure, potential money laundering facilitation

---

## Summary of Suspicious Activity

Independent security research of the **Huione Pay** mobile application has identified technical indicators consistent with a platform designed to facilitate financial fraud, money laundering, and potentially operate as infrastructure for cybercrime:

### 1. Blockchain-Based Command & Control
The application uses a **Binance Smart Chain smart contract** to store its server URL on-chain — a technique providing censorship-resistant infrastructure. This pattern is documented in financially-motivated malware families.

- Contract: `0xe9d5f645f79fa60fca82b4e1d35832e43370feb0` (BSC)
- C2 URL stored on-chain: `https://8kwfaa30jtlnwi.com`

### 2. Mixing Contract Pattern
A connected BSC contract (`0x000037bb05b2cef17c6469f4bcdb198826ce0000`) holds **~$31,800 USD in BNB** and implements a `bulkWithdraw(amounts[], recipients[])` function — the technical signature of a cryptocurrency mixing/tumbling service.

### 3. Security Vulnerabilities Enabling Fraud
The application contains critical security vulnerabilities consistent with intentional design for fraud facilitation:
- Hardcoded encryption key (any employee can decrypt user traffic)
- IDOR vulnerability allowing account impersonation
- Withdrawal address manipulation capability
- OTP bypass enabling account takeover

### 4. Infrastructure Indicators
- Direct backend IP (`8.217.236.122:19003`) hosted outside CDN protections
- MQTT real-time trading data exposed with hardcoded credentials
- S3 bucket exposing server configuration publicly

### 5. Geographic Concern
Application server infrastructure geolocates to **Cambodia** (IP: `119.13.56.36`), consistent with known Southeast Asian cybercrime operational geography.

---

## Technical Evidence

All findings supported by:
- Timestamped HTTP probe results with SHA256 hashes
- On-chain transaction records (BSC — publicly verifiable)
- Decompiled application binary analysis
- Network traffic captures (decrypted using extracted key)

---

## Recommended FinCEN Actions

1. Issue guidance to U.S. financial institutions regarding Huione Pay transactions
2. Coordinate with BSC/Binance regarding smart contract cluster
3. Share intelligence with CISA and relevant international partners
4. Coordinate with DOJ Cybercrime unit for smart contract seizure evaluation

---

## Reporter Information

Independent Security Researcher  
Contact: security-research@proton.me  
Full technical report available upon request  

*This report is submitted in good faith based on technical findings. The reporter makes no legal conclusions and defers to FinCEN's authority for regulatory determination.*
