# CVE-Pending: Multi-Signature Race Condition

**Severity:** Critical | **CVSS:** 9.0 | **CWE:** CWE-362 (Race Condition)

## Vulnerability Summary

The multi-signature transfer workflow in Huione Pay is vulnerable to a race condition. The signing endpoint (`/foundation/sign/batchTransfer/sign`) does not implement atomic state transitions, allowing an attacker with a valid signer token to submit a signature before other required signers have approved.

## Affected Endpoints

```
POST /multiSign/batchTransfer           - Create batch transfer
POST /foundation/sign/batchTransfer/sign - Sign a transfer
POST /foundation/sign/batchTransfer/queryOne - Query transfer state
```

## Technical Detail

```
Expected flow (M-of-N multi-sig):
  1. Initiator creates batch transfer → status: PENDING
  2. All N signers must approve sequentially
  3. Transfer executes only after quorum reached

Vulnerable flow (race condition):
  1. Attacker observes PENDING transfer via queryOne
  2. Concurrent signing requests bypass sequential check
  3. Server processes first-received signature without quorum
  → Transfer executes with insufficient approvals
```

**Root cause:** The `batchTransferSignStatus` field is read and updated in non-atomic operations. No distributed lock or optimistic concurrency control is implemented.

## Impact

- Financial: Unauthorized multi-signature transfers can be executed
- Severity amplified by large transaction sizes typical in enterprise Huione Chain accounts

## Remediation

1. Implement database-level row locking during signature state transitions
2. Use optimistic concurrency control (compare-and-swap on `signatureVersion`)
3. Add server-side quorum check as a single atomic transaction
4. Implement signing rate limiting per signer per transfer

## Disclosure Timeline

- **2026-02-15**: Vulnerability identified via API endpoint analysis
- **2026-03-10**: Included in responsible disclosure package
- **Status**: Awaiting vendor response
