# CVE-Pending: Client-Side Permission Model (No Server Enforcement)

**Severity:** High | **CVSS:** 8.1 | **CWE:** CWE-602 (Client-Side Enforcement of Server-Side Security)

## Vulnerability Summary

Huione Pay stores user permission flags as plain strings in SharedPreferences and local cache. The server does not validate whether a user actually holds permissions before executing sensitive operations — it trusts client-supplied permission state.

## Affected Permissions (from libapp.so decompilation)

```
permissions.withdraw.wallet
permissions.transfer
permissions.deposit
permissions.deposit.ap
permissions.deposit.chain
permissions.withdraw
permissions.withdraw.bank_card
permissions.withdraw.thunes
```

## Technical Detail

```
Observed behavior:
  - Permissions are fetched from /foundation/user/userInfo response
  - Stored locally in SharedPreferences as string key-value pairs
  - UI feature gates check local store only
  - Server API endpoints do not re-validate permission on each call

Evidence:
  - Decompiled pp.txt contains permission key names
  - /foundation/user/userInfo response body includes permissions array
  - Restricted endpoints return 200 OK regardless of permission state
```

## Impact

- Users with restricted accounts can access withdrawal, transfer, deposit operations
- Account tier restrictions are bypassable at the client level

## Remediation

1. Move all permission checks server-side — never trust client-provided permission state
2. Validate permissions at the API gateway level on each request
3. Remove permission data from client-accessible storage
4. Implement server-side role-based access control (RBAC)

## Disclosure Timeline

- **2026-02-15**: Identified during static analysis of permission handling code
- **2026-03-10**: Included in responsible disclosure package
- **Status**: Awaiting vendor response
