# CVE-Pending: Withdraw Address Book — Weak Authentication (IDOR)

**Severity:** Critical | **CVSS:** 9.1 | **CWE:** CWE-639 (IDOR via Direct Reference)

## Vulnerability Summary

The withdrawal address book endpoints in Huione Pay lack proper authorization checks. An authenticated user can add, modify, query, and delete address book entries using only a valid JWT token, without fund password verification for destructive operations.

## Affected Endpoints

```
POST /home/withdraw/wallet/address          - List wallet addresses
POST /home/withdraw/wallet/address/add      - Add new address
POST /foundation/addressbook/query          - Query address book
POST /foundation/addressbook/add            - Add to address book
POST /foundation/addressbook/updateRemark   - Update address remark (no auth)
POST /foundation/addressbook/delete         - Delete address (no auth)
```

## Technical Detail

```
Expected flow:
  - Adding/modifying withdrawal addresses should require fund password (fundPassword)
  - Delete operation should require 2FA confirmation

Observed behavior:
  - /foundation/addressbook/updateRemark accepts changes without fundPassword
  - /foundation/addressbook/delete executes without additional verification
  - /foundation/addressbook/add does not rate-limit address additions
  - No CSRF token or request signing on address book mutations

IDOR vector:
  - Address book entries use sequential or guessable IDs
  - No ownership verification: any valid token can reference any address ID
```

## Impact

- **Financial theft vector**: Attacker with temporary account access can pre-add attacker-controlled withdrawal addresses
- **Persistence**: Even after JWT expiry, pre-added address remains in victim's book
- Combined with social engineering: victim is tricked into using "trusted" pre-added address

## Remediation

1. Require fund password for all address book mutations (add/edit/delete)
2. Implement ownership check: verify address belongs to authenticated user
3. Add server-side rate limiting on address additions
4. Send OTP notification on new withdrawal address additions
5. Implement address whitelist with cooling period (e.g., 24h before new address is usable)

## Disclosure Timeline

- **2026-02-15**: Identified during API endpoint analysis
- **2026-03-10**: Included in responsible disclosure package
- **Status**: Awaiting vendor response
