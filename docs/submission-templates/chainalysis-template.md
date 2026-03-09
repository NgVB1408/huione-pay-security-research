# Chainalysis Intelligence Submission
# Huione Pay — Blockchain C2 Infrastructure & Financial Crime Evidence

**Submission Type:** Threat Intelligence  
**Priority:** High  
**Date:** March 2026  

---

## Executive Summary

Security research into the **Huione Pay** Android application has uncovered a sophisticated blockchain-based Command & Control (C2) infrastructure deployed on Binance Smart Chain (BSC). The infrastructure uses an immutable smart contract as a dead-drop resolver — a technique increasingly adopted by financially-motivated threat actors to maintain operational resilience against domain seizures and law enforcement takedowns.

Additionally, on-chain analysis reveals a network of smart contracts and wallets holding significant BNB balances (~$31,000+ USD) connected to this infrastructure.

---

## Blockchain Infrastructure Map

### BSC Smart Contract — C2 URL Resolver

```
Contract:  0xe9d5f645f79fa60fca82b4e1d35832e43370feb0
Chain:     Binance Smart Chain (BSC)
Type:      Proxy / URL storage contract
Owner:     0x849008a657e7b48e993d8ffd5c7ad29c95598905
Function:  getUrl() → "https://8kwfaa30jtlnwi.com"
Deployed:  Nonce = 1 (single deployment)
```

**On-chain evidence:**
```json
{
  "method": "eth_call",
  "params": [{"to": "0xe9d5f645f79fa60fca82b4e1d35832e43370feb0", "data": "0x20965255"}],
  "result": "https://8kwfaa30jtlnwi.com"
}
```

### Associated Wallet / Contract Cluster

```
┌─────────────────────────────────────────────────────────────┐
│                  HUIONE BSC CLUSTER                         │
├──────────────────────────────────────┬───────────┬──────────┤
│ Address                              │ Balance   │ Type     │
├──────────────────────────────────────┼───────────┼──────────┤
│ 0xe9d5f645f79fa60fca82b4e1d35832e4.. │ 0 BNB     │ C2 Smart │
│ 0x849008a657e7b48e993d8ffd5c7ad29c.. │ 0.031 BNB │ C2 Owner │
│ 0x000037bb05b2cef17c6469f4bcdb1988.. │ 49.6 BNB  │ Mid Cont.│
│ 0x0000e23abdc862a1911d77904e77fdb3.. │ 0 BNB     │ Storage  │
│ 0xAaFe0f12bd88a82dE30765df0C244f11.. │ 0 BNB     │ Target   │
└──────────────────────────────────────┴───────────┴──────────┘
```

### Mid Contract — Bulk Withdrawal (Mixer Pattern)

```
Address:  0x000037bb05b2cef17c6469f4bcdb198826ce0000
Balance:  49.666 BNB (~$31,795 USD) — ACTIVE
ABI:      withdraw(uint256, address)
          bulkWithdraw(uint256[], address[])  ← MIXER FUNCTION
          fallback() payable
          receive() payable
```

The `bulkWithdraw()` function pattern — accepting arrays of amounts and recipient addresses — is characteristic of **on-chain mixing/tumbling** services used to obfuscate fund flows.

---

## Threat Attribution Indicators

### Infrastructure Overlap

| Indicator | Type | Confidence |
|-----------|------|-----------|
| `app.hh3721.com` | Domain | High |
| `8kwfaa30jtlnwi.com` | C2 Domain | High |
| `8.217.236.122:19003` | IP:Port | High |
| `cancelaccount-h5.oykqk.com` | Phishing domain | High |
| `wss-mqtt.xone.la` | MQTT broker | Medium |
| `datadogips.s3.ap-southeast-1.amazonaws.com` | S3 config | High |
| BSC: `0xe9d5f...feb0` | Smart contract | Confirmed |

### Geographic Attribution
- Server IP `119.13.56.36` geolocates to **Phnom Penh, Cambodia**
- ISP: Viettel Cambodia (ASN 38623)
- Consistent with known Huione Group operational geography

### MQTT Intelligence
- Broker: `wss://wss-mqtt.xone.la:443/mqtt`
- Credentials: `mt5_user / Qwer1234` (hardcoded in app)
- Data observed: Real-time trading data for USDT/USD, JB2/USDH, HOC pairs
- Message rate: ~4,383 messages/15 seconds (>290 msg/s)

---

## Relevance to Financial Crime

Huione Group has been publicly identified in connection with:
- Cryptocurrency romance scam ("pig butchering") facilitation
- Money laundering infrastructure for Southeast Asian cybercrime
- OFAC designation proceedings (referenced in public reporting)

The technical infrastructure documented here provides on-chain evidence linking the mobile application to:
1. BSC smart contract cluster (blockchain-based C2)
2. Active fund holdings (~$31,795 in Mid Contract)
3. Mixer-pattern contract (`bulkWithdraw`)
4. Multiple active phishing domains

---

## Recommended Actions

1. **Trace BSC cluster** — Follow fund flows from Mid Contract (`0x000037bb...`)
2. **Cross-chain analysis** — Investigate USDH flows across Huione Chain ↔ BSC ↔ Tron
3. **Domain intelligence** — Map full domain cluster around `hh3721.com`, `8kwfaa30jtlnwi.com`
4. **MQTT data** — Monitor `wss-mqtt.xone.la` for trading pattern intelligence
5. **Alert exchanges** — Notify BSC-listed exchanges of associated wallet addresses

---

## Evidence Files

- `infrastructure-proof/evidence-capture.json` — Timestamped HTTP probes (SHA256 verified)
- `research/blockchain-infra.md` — Full on-chain analysis
- `VULNERABILITY_REPORT.md` — Complete security assessment

---

*Submitted to Chainalysis Intelligence Team for analysis and cross-referencing with existing threat intelligence.*
*Contact: security-research@proton.me*
