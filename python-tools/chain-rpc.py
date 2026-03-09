#!/usr/bin/env python3
"""
chain_rpc.py - Huione Chain RPC Client
========================================
JSON-RPC 2.0 client cho Huione Chain (Solana fork).

Huione Chain la fork cua Solana nen tuong thich 100% voi Solana JSON-RPC API.
Node Huione expose RPC qua CLI params:
  --rpc-port 8899        (default HTTP)
  --rpc-bind-address 0.0.0.0
  --enable-rpc-transaction-history

RPC Endpoints:
  Local:   http://localhost:8899
  Public:  https://rpc.huione.org  (co the bi geo-restricted)
  DevNet:  https://devnet.huione.com (dev/test)

WebSocket PubSub:
  Local:   ws://localhost:8900
  Public:  wss://rpc.huione.org

Native Token: HC (1 lamport = 0.000000001 HC)

Usage:
  python chain_rpc.py --health                          # Check node health
  python chain_rpc.py --info                            # Node version + slot info
  python chain_rpc.py --balance <address>               # Query HC balance
  python chain_rpc.py --tx <signature>                  # Get transaction details
  python chain_rpc.py --block <slot>                    # Get block by slot
  python chain_rpc.py --verify-tx <signature>           # Verify a transaction exists on-chain
  python chain_rpc.py --rpc http://your-node:8899       # Use custom RPC endpoint
  python chain_rpc.py --scan-latest 10                  # Scan latest N blocks
"""

import argparse
import json
import sys
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============================================================
# CONSTANTS
# ============================================================

# Default RPC endpoints
RPC_ENDPOINTS = {
    "local": "http://localhost:8899",
    "public": "https://rpc.huione.org",
    "devnet": "https://devnet.huione.com",
}

# WebSocket PubSub endpoints
WS_ENDPOINTS = {
    "local": "ws://localhost:8900",
    "public": "wss://rpc.huione.org",
}

# HC token decimals (like SOL: 1 HC = 10^9 lamports)
LAMPORTS_PER_HC = 1_000_000_000

# Validator CLI reference
VALIDATOR_CLI_PARAMS = {
    "--rpc-port": "Port for JSON-RPC HTTP service (default: 8899)",
    "--rpc-bind-address": "IP address to bind RPC service (default: 127.0.0.1)",
    "--private-rpc": "Do not publish RPC port in gossip network",
    "--enable-rpc-transaction-history": "Enable historical transaction query via RPC",
    "--limit-ledger-size": "Limit ledger storage size",
    "--entrypoint": "Network entrypoint address (host:port)",
    "--identity": "Validator identity keypair file",
    "--vote-account": "Vote account keypair file",
    "--ledger": "Ledger data directory",
}


# ============================================================
# HUIONE CHAIN RPC CLIENT
# ============================================================

class HuioneRPC:
    """
    JSON-RPC 2.0 client for Huione Chain.
    Compatible with Solana RPC methods since Huione is a Solana fork.
    """

    def __init__(self, endpoint=None, timeout=15):
        if not HAS_REQUESTS:
            raise ImportError("requests required: pip install requests")

        self.endpoint = endpoint or RPC_ENDPOINTS["local"]
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
        self._request_id = 0

    def _next_id(self):
        self._request_id += 1
        return self._request_id

    def _call(self, method, params=None):
        """Make JSON-RPC 2.0 call."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or [],
        }

        try:
            resp = self.session.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                return {
                    "error": f"HTTP {resp.status_code}",
                    "body": resp.text[:500],
                }

            result = resp.json()

            if "error" in result:
                return {"error": result["error"]}

            return result.get("result", result)

        except requests.exceptions.ConnectionError:
            return {"error": f"Connection refused: {self.endpoint}"}
        except requests.exceptions.Timeout:
            return {"error": f"Timeout ({self.timeout}s): {self.endpoint}"}
        except Exception as e:
            return {"error": str(e)}

    # ========================================
    # CLUSTER INFO
    # ========================================

    def get_health(self):
        """Check if the node is healthy."""
        return self._call("getHealth")

    def get_version(self):
        """Get node software version."""
        return self._call("getVersion")

    def get_slot(self):
        """Get current slot (block height equivalent)."""
        return self._call("getSlot")

    def get_block_height(self):
        """Get current block height."""
        return self._call("getBlockHeight")

    def get_epoch_info(self):
        """Get current epoch information."""
        return self._call("getEpochInfo")

    def get_cluster_nodes(self):
        """Get list of cluster nodes."""
        return self._call("getClusterNodes")

    def get_supply(self):
        """Get total HC supply."""
        return self._call("getSupply")

    def get_recent_blockhash(self):
        """Get recent blockhash (needed for transactions)."""
        return self._call("getRecentBlockhash")

    def get_genesis_hash(self):
        """Get genesis block hash."""
        return self._call("getGenesisHash")

    # ========================================
    # ACCOUNT QUERIES
    # ========================================

    def get_balance(self, pubkey):
        """Get HC balance for an address (in lamports)."""
        result = self._call("getBalance", [pubkey])
        if isinstance(result, dict) and "value" in result:
            lamports = result["value"]
            return {
                "pubkey": pubkey,
                "lamports": lamports,
                "hc": lamports / LAMPORTS_PER_HC,
            }
        return result

    def get_account_info(self, pubkey, encoding="jsonParsed"):
        """Get full account info."""
        return self._call("getAccountInfo", [
            pubkey,
            {"encoding": encoding},
        ])

    def get_token_accounts_by_owner(self, owner_pubkey, mint=None, program_id=None):
        """Get SPL token accounts owned by a pubkey."""
        filter_obj = {}
        if mint:
            filter_obj = {"mint": mint}
        elif program_id:
            filter_obj = {"programId": program_id}
        else:
            # Default: Token Program ID (same as Solana SPL Token)
            filter_obj = {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}

        return self._call("getTokenAccountsByOwner", [
            owner_pubkey,
            filter_obj,
            {"encoding": "jsonParsed"},
        ])

    def get_token_balance(self, token_account_pubkey):
        """Get SPL token balance for a token account."""
        return self._call("getTokenAccountBalance", [token_account_pubkey])

    # ========================================
    # TRANSACTION QUERIES
    # ========================================

    def get_transaction(self, signature, encoding="jsonParsed"):
        """
        Get transaction details by signature.
        This is the key method for VERIFYING on-chain transactions.
        """
        return self._call("getTransaction", [
            signature,
            {"encoding": encoding, "maxSupportedTransactionVersion": 0},
        ])

    def get_signatures_for_address(self, address, limit=10, before=None):
        """Get recent transaction signatures for an address."""
        opts = {"limit": limit}
        if before:
            opts["before"] = before
        return self._call("getSignaturesForAddress", [address, opts])

    def get_confirmed_transaction(self, signature):
        """Get confirmed transaction (legacy method)."""
        return self._call("getConfirmedTransaction", [signature, "jsonParsed"])

    # ========================================
    # BLOCK QUERIES
    # ========================================

    def get_block(self, slot, encoding="jsonParsed"):
        """Get block by slot number."""
        return self._call("getBlock", [
            slot,
            {"encoding": encoding, "maxSupportedTransactionVersion": 0,
             "transactionDetails": "full", "rewards": False},
        ])

    def get_block_time(self, slot):
        """Get estimated production time of a block."""
        return self._call("getBlockTime", [slot])

    def get_blocks(self, start_slot, end_slot=None):
        """Get list of confirmed blocks between two slots."""
        params = [start_slot]
        if end_slot:
            params.append(end_slot)
        return self._call("getBlocks", params)

    # ========================================
    # FORENSIC HELPERS
    # ========================================

    def verify_transaction(self, signature):
        """
        Verify that a transaction exists on-chain and is confirmed.
        Returns verification result with details.
        """
        tx = self.get_transaction(signature)

        if isinstance(tx, dict) and "error" in tx:
            return {
                "signature": signature,
                "verified": False,
                "reason": f"RPC error: {tx['error']}",
            }

        if tx is None:
            return {
                "signature": signature,
                "verified": False,
                "reason": "Transaction not found on-chain",
            }

        # Extract key info
        meta = tx.get("meta", {}) if isinstance(tx, dict) else {}
        slot = tx.get("slot") if isinstance(tx, dict) else None
        block_time = tx.get("blockTime") if isinstance(tx, dict) else None

        err = meta.get("err") if isinstance(meta, dict) else None

        result = {
            "signature": signature,
            "verified": True,
            "slot": slot,
            "block_time": block_time,
            "block_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(block_time)) if block_time else None,
            "status": "failed" if err else "confirmed",
            "error": err,
            "fee_lamports": meta.get("fee") if isinstance(meta, dict) else None,
        }

        # Extract transfer amounts if available
        if isinstance(meta, dict):
            pre = meta.get("preBalances", [])
            post = meta.get("postBalances", [])
            if pre and post and len(pre) == len(post):
                changes = []
                for i, (p, q) in enumerate(zip(pre, post)):
                    diff = q - p
                    if diff != 0:
                        changes.append({
                            "account_index": i,
                            "change_lamports": diff,
                            "change_hc": diff / LAMPORTS_PER_HC,
                        })
                result["balance_changes"] = changes

        return result

    def scan_latest_blocks(self, count=5):
        """Scan the latest N blocks and summarize transactions."""
        current_slot = self.get_slot()
        if isinstance(current_slot, dict) and "error" in current_slot:
            return current_slot

        results = []
        slot = current_slot

        for _ in range(count):
            block = self.get_block(slot)
            if isinstance(block, dict) and "error" not in block:
                tx_count = len(block.get("transactions", []))
                block_time = block.get("blockTime")
                results.append({
                    "slot": slot,
                    "transactions": tx_count,
                    "block_time": block_time,
                    "block_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime(block_time)) if block_time else None,
                })
            slot -= 1

        return {
            "current_slot": current_slot,
            "blocks_scanned": len(results),
            "blocks": results,
        }

    def get_node_info(self):
        """Get comprehensive node information."""
        version = self.get_version()
        slot = self.get_slot()
        height = self.get_block_height()
        health = self.get_health()
        epoch = self.get_epoch_info()
        genesis = self.get_genesis_hash()

        return {
            "endpoint": self.endpoint,
            "health": health,
            "version": version,
            "slot": slot,
            "block_height": height,
            "epoch_info": epoch,
            "genesis_hash": genesis,
        }


# ============================================================
# CLI
# ============================================================

def format_json(obj):
    """Pretty-print JSON."""
    return json.dumps(obj, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Huione Chain RPC Client (Solana-compatible JSON-RPC 2.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
RPC Endpoints:
  Local:   http://localhost:8899  (default, run your own node)
  Public:  https://rpc.huione.org (may be geo-restricted)
  DevNet:  https://devnet.huione.com

Validator CLI (to run your own node):
  huione-validator \\
    --identity ~/validator-keypair.json \\
    --vote-account ~/vote-account-keypair.json \\
    --ledger ./ledger \\
    --rpc-port 8899 \\
    --rpc-bind-address 0.0.0.0 \\
    --enable-rpc-transaction-history

Examples:
  python chain_rpc.py --health
  python chain_rpc.py --info
  python chain_rpc.py --balance <HC_ADDRESS>
  python chain_rpc.py --tx <TX_SIGNATURE>
  python chain_rpc.py --verify-tx <TX_SIGNATURE>
  python chain_rpc.py --scan-latest 10
  python chain_rpc.py --rpc https://rpc.huione.org --info
        """,
    )

    # Connection
    parser.add_argument("--rpc", default=None,
                        help="RPC endpoint URL (default: http://localhost:8899)")
    parser.add_argument("--timeout", type=int, default=15,
                        help="Request timeout in seconds")

    # Commands
    parser.add_argument("--health", action="store_true",
                        help="Check node health")
    parser.add_argument("--info", action="store_true",
                        help="Get node version, slot, epoch info")
    parser.add_argument("--balance", metavar="ADDRESS",
                        help="Get HC balance for address")
    parser.add_argument("--account", metavar="ADDRESS",
                        help="Get full account info")
    parser.add_argument("--tokens", metavar="OWNER_ADDRESS",
                        help="Get SPL token accounts for owner")
    parser.add_argument("--tx", metavar="SIGNATURE",
                        help="Get transaction details")
    parser.add_argument("--verify-tx", metavar="SIGNATURE",
                        help="Verify transaction exists on-chain")
    parser.add_argument("--history", metavar="ADDRESS",
                        help="Get recent transaction signatures for address")
    parser.add_argument("--block", metavar="SLOT", type=int,
                        help="Get block by slot number")
    parser.add_argument("--scan-latest", metavar="N", type=int,
                        help="Scan latest N blocks")
    parser.add_argument("--supply", action="store_true",
                        help="Get total HC supply")
    parser.add_argument("--genesis", action="store_true",
                        help="Get genesis block hash")
    parser.add_argument("--nodes", action="store_true",
                        help="List cluster nodes")
    parser.add_argument("--validator-help", action="store_true",
                        help="Show huione-validator CLI reference")

    # Batch verification
    parser.add_argument("--verify-file", metavar="FILE",
                        help="Verify transactions from file (one txId per line)")

    args = parser.parse_args()

    # Validator help (no RPC needed)
    if args.validator_help:
        print("=" * 60)
        print("  huione-validator CLI Reference")
        print("=" * 60)
        for param, desc in VALIDATOR_CLI_PARAMS.items():
            print(f"  {param:45s}  {desc}")
        print("\nExample:")
        print("  huione-validator \\")
        print("    --identity ~/validator-keypair.json \\")
        print("    --vote-account ~/vote-account-keypair.json \\")
        print("    --ledger ./ledger \\")
        print("    --rpc-port 8899 \\")
        print("    --rpc-bind-address 0.0.0.0 \\")
        print("    --enable-rpc-transaction-history")
        print("=" * 60)
        return

    # Initialize RPC client
    endpoint = args.rpc or RPC_ENDPOINTS["local"]
    rpc = HuioneRPC(endpoint=endpoint, timeout=args.timeout)

    print(f"[*] RPC endpoint: {endpoint}", file=sys.stderr)

    # Execute command
    if args.health:
        result = rpc.get_health()
        print(format_json(result))

    elif args.info:
        result = rpc.get_node_info()
        print(format_json(result))

    elif args.balance:
        result = rpc.get_balance(args.balance)
        if isinstance(result, dict) and "hc" in result:
            print(f"Address:  {result['pubkey']}")
            print(f"Balance:  {result['hc']:.9f} HC")
            print(f"Lamports: {result['lamports']}")
        else:
            print(format_json(result))

    elif args.account:
        result = rpc.get_account_info(args.account)
        print(format_json(result))

    elif args.tokens:
        result = rpc.get_token_accounts_by_owner(args.tokens)
        print(format_json(result))

    elif args.tx:
        result = rpc.get_transaction(args.tx)
        print(format_json(result))

    elif args.verify_tx:
        result = rpc.verify_transaction(args.verify_tx)
        if result["verified"]:
            print(f"[VERIFIED] Transaction confirmed on-chain")
            print(f"  Signature:  {result['signature'][:40]}...")
            print(f"  Slot:       {result['slot']}")
            print(f"  Time:       {result['block_time_iso']}")
            print(f"  Status:     {result['status']}")
            print(f"  Fee:        {result['fee_lamports']} lamports")
            if result.get("balance_changes"):
                print(f"  Changes:")
                for c in result["balance_changes"]:
                    sign = "+" if c["change_hc"] > 0 else ""
                    print(f"    Account[{c['account_index']}]: {sign}{c['change_hc']:.9f} HC")
        else:
            print(f"[NOT FOUND] {result['reason']}")
        print()
        print(format_json(result))

    elif args.history:
        result = rpc.get_signatures_for_address(args.history)
        if isinstance(result, list):
            print(f"Recent transactions for {args.history}:")
            for sig in result:
                err = sig.get("err")
                status = "FAIL" if err else "OK"
                slot = sig.get("slot", "?")
                bt = sig.get("blockTime")
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(bt)) if bt else "?"
                print(f"  [{status}] {sig['signature'][:40]}...  slot={slot}  time={ts}")
        else:
            print(format_json(result))

    elif args.block is not None:
        result = rpc.get_block(args.block)
        if isinstance(result, dict) and "error" not in result:
            txs = result.get("transactions", [])
            bt = result.get("blockTime")
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(bt)) if bt else "?"
            print(f"Block at slot {args.block}:")
            print(f"  Time:         {ts}")
            print(f"  Transactions: {len(txs)}")
            print(f"  Parent slot:  {result.get('parentSlot')}")
            # Print first few transactions
            for i, tx in enumerate(txs[:10]):
                sig = tx.get("transaction", {}).get("signatures", ["?"])[0]
                print(f"  TX[{i}]: {sig[:50]}...")
        else:
            print(format_json(result))

    elif args.scan_latest:
        result = rpc.scan_latest_blocks(args.scan_latest)
        if isinstance(result, dict) and "blocks" in result:
            print(f"Current slot: {result['current_slot']}")
            print(f"Scanned {result['blocks_scanned']} blocks:\n")
            for b in result["blocks"]:
                print(f"  Slot {b['slot']:>12d}  |  {b['transactions']:>4d} txs  |  {b.get('block_time_iso', '?')}")
        else:
            print(format_json(result))

    elif args.supply:
        result = rpc.get_supply()
        print(format_json(result))

    elif args.genesis:
        result = rpc.get_genesis_hash()
        print(f"Genesis hash: {result}")

    elif args.nodes:
        result = rpc.get_cluster_nodes()
        if isinstance(result, list):
            print(f"Cluster nodes ({len(result)}):")
            for node in result:
                pubkey = node.get("pubkey", "?")[:20]
                rpc_addr = node.get("rpc") or "no-rpc"
                version = node.get("version") or "?"
                print(f"  {pubkey}...  rpc={rpc_addr}  version={version}")
        else:
            print(format_json(result))

    elif args.verify_file:
        print(f"[*] Batch verifying transactions from {args.verify_file}")
        verified = 0
        not_found = 0
        errors = 0

        with open(args.verify_file, "r") as f:
            for line in f:
                sig = line.strip()
                if not sig or sig.startswith("#"):
                    continue

                result = rpc.verify_transaction(sig)
                if result["verified"]:
                    print(f"  [OK]    {sig[:40]}...  slot={result['slot']}")
                    verified += 1
                else:
                    print(f"  [MISS]  {sig[:40]}...  {result['reason']}")
                    not_found += 1

        total = verified + not_found + errors
        print(f"\nResults: {verified}/{total} verified, {not_found} not found, {errors} errors")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
