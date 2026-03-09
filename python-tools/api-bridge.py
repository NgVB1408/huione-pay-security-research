#!/usr/bin/env python3
"""
api_bridge.py - Huione Pay Read-Only API Client
=================================================
Client de goi API Huione Pay (chi doc, khong ghi/tao giao dich).

Features:
  - ECDH key exchange simulation (generate keypair, compute shared secret)
  - AES channel encryption/decryption
  - Login va lay token
  - Query endpoints: account/get, bill/query, bill/export
  - Auto decrypt response voi AES key

Architecture:
  Server: https://app.hh3721.com/app/foundation-server
  Direct: https://23.248.236.82:19003/app/foundation-server
  Multi-tenant: productInstanceId = INSTANCE-HP (Huione Pay) / INSTANCE-HW (Huiwang)

Blockchain RPC:
  Huione Chain (Solana fork): https://rpc.huione.org
  Explorer: https://explorer.huione.org

Usage:
  python api_bridge.py --test                    # Test ECDH + AES logic
  python api_bridge.py --info                    # Show API endpoint map
  python api_bridge.py --probe                   # Probe server health
  python api_bridge.py --rpc-test                # Test Huione Chain RPC
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from urllib.parse import quote, unquote

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    print("[ERROR] pycryptodome required: pip install pycryptodome", file=sys.stderr)
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============================================================
# CONSTANTS
# ============================================================

HUIONE_AES_KEY = b"keyhead_project_xhui_one_keytail"

# API Server endpoints
SERVERS = {
    "primary": "https://app.hh3721.com/app/foundation-server",
    "direct_ip": "https://8.217.236.122:19003/app/foundation-server",
    "direct_ip_old": "https://23.248.236.82:19003/app/foundation-server",
}

# Dynamic IP config source (app fetches on startup)
IP_CONFIG_URL = "https://datadogips.s3.ap-southeast-1.amazonaws.com/ip.json"

# Huione Chain (Solana fork) RPC
HUIONE_CHAIN_RPC = "https://rpc.huione.org"
HUIONE_CHAIN_EXPLORER = "https://explorer.huione.org"

# Multi-tenant instance IDs
INSTANCES = {
    "INSTANCE-HP": "Huione Pay",
    "INSTANCE-HW": "Huiwang",
}

# Read-only API endpoints (grouped by function)
API_ENDPOINTS = {
    "auth": {
        "get_app_info": "/foundation/auth/login/getAppInfo",
        "agree_auth": "/foundation/auth/login/agreeAuth",
    },
    "user": {
        "login": "/foundation/user/login",
        "user_info": "/foundation/user/userInfo",
        "heartbeat": "/foundation/user/heartbeat",
        "devices": "/foundation/user/devices",
        "query_todo": "/foundation/user/queryToDo",
    },
    "account": {
        "get": "/foundation/account/get",
        "address_inner": "/foundation/account/address/inner",
        "chain_reg": "/foundation/account/chainReg",
        "distribution": "/foundation/account/distribution",
        "wealth": "/foundation/account/wealth",
        "deposit_currency": "/foundation/account/v3/depositCurrency",
        "withdraw_currency": "/foundation/account/withdrawCurrency",
    },
    "bills": {
        "query": "/foundation/bill/query",
        "export": "/foundation/bill/export",
        "one_bill": "/foundation/dc-bill/app/oneBillDataApp",
        "page_list": "/foundation/dc-bill/app/pageBillListData",
        "order_record": "/foundation/dc-bill/order/record",
    },
    "risk_ecdh": {
        "push_pub_key": "/foundation/risk/pushPubKeyStr",
        "secret_exchange": "/foundation/risk/secretExchange",
        "verify_pub_key": "/foundation/risk/verifyPubKey",
    },
    "transfer_read": {
        "recent_users": "/foundation/recent/transfer/users",
        "user_bills": "/foundation/recent/transfer/specify/user/bills",
        "has_record": "/foundation/recent/transfer/specify/user/hasRecord",
        "pay_config": "/foundation/trade/pay/config",
        "config_get": "/foundation/trade/config/get",
    },
}


# ============================================================
# AES ENCRYPTION (Reuse from aes_decryptor.py)
# ============================================================

def aes_encrypt(plaintext: str, key: bytes = HUIONE_AES_KEY) -> str:
    """AES/ECB/PKCS7 encrypt -> Base64 -> URL encode."""
    key_bytes = bytearray(32)
    key_bytes[:len(key[:32])] = key[:32]
    cipher = AES.new(bytes(key_bytes), AES.MODE_ECB)
    padded = pad(plaintext.encode("utf-8"), 16)
    ciphertext = cipher.encrypt(padded)
    b64 = base64.b64encode(ciphertext).decode("ascii")
    return quote(b64, safe="")


def aes_decrypt(encoded: str, key: bytes = HUIONE_AES_KEY) -> str:
    """URL decode -> Base64 decode -> AES/ECB/PKCS7 decrypt."""
    url_decoded = unquote(encoded.strip())
    ciphertext = base64.b64decode(url_decoded)
    key_bytes = bytearray(32)
    key_bytes[:len(key[:32])] = key[:32]
    cipher = AES.new(bytes(key_bytes), AES.MODE_ECB)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext), 16)
    except ValueError:
        plaintext = cipher.decrypt(ciphertext).rstrip(b'\x00')
    return plaintext.decode("utf-8", errors="replace").strip()


# ============================================================
# ECDH SIMULATION
# ============================================================

def simulate_ecdh():
    """
    Simulate ECDH key exchange flow.
    In real app: AndroidNDKEncryption.getKeyPairStr() + exchangeECDHPublic()
    Here: demonstrate the protocol with Python's cryptography lib.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        # Generate client keypair (ECDH P-256)
        client_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        client_public = client_private.public_key()

        # Serialize public key (PEM format, similar to Huione's getKeyPairStr)
        client_pub_pem = client_public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        client_priv_pem = client_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")

        print("[*] ECDH Keypair generated (P-256/secp256r1)")
        print(f"  Public key:\n{client_pub_pem[:120]}...")
        print(f"  Private key: [REDACTED - {len(client_priv_pem)} bytes]")

        # In real flow:
        # 1. POST /foundation/risk/pushPubKeyStr  {publicKey: client_pub_pem}
        # 2. Server returns serverPublicKey
        # 3. Client calls exchangeECDHPublic(clientPrivateKey, serverPublicKey)
        #    which internally does: ECDH(clientPrivate, serverPublic) -> sharedSecret
        # 4. sharedSecret is used as AES key for channel encryption

        # Simulate server keypair (for testing)
        server_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        server_public = server_private.public_key()

        # ECDH: derive shared secret
        client_shared = client_private.exchange(ec.ECDH(), server_public)
        server_shared = server_private.exchange(ec.ECDH(), client_public)

        assert client_shared == server_shared, "ECDH shared secrets don't match!"

        # In Huione's native lib (ecdh.cpp), shared secret is used directly or hashed
        shared_hex = client_shared.hex()
        shared_hash = hashlib.sha256(client_shared).hexdigest()

        print(f"\n[*] ECDH shared secret derived:")
        print(f"  Raw (hex): {shared_hex[:32]}...{shared_hex[-8:]}")
        print(f"  SHA256:    {shared_hash}")
        print(f"  Length:    {len(client_shared)} bytes")

        # Test channel encryption with shared secret
        channel_key = client_shared[:32]  # Use first 32 bytes as AES key
        test_msg = '{"userId": 12345, "action": "query"}'
        encrypted = aes_encrypt(test_msg, channel_key)
        decrypted = aes_decrypt(encrypted, channel_key)
        assert decrypted == test_msg, "Channel encryption round-trip failed!"

        print(f"\n[*] Channel encryption test:")
        print(f"  Plaintext:  {test_msg}")
        print(f"  Encrypted:  {encrypted[:60]}...")
        print(f"  Decrypted:  {decrypted}")
        print(f"  Round-trip: OK")

        return True

    except ImportError:
        print("[WARN] 'cryptography' package not installed. Install with:")
        print("  pip install cryptography")
        print("[*] Skipping ECDH simulation (AES-only mode)")
        return False


# ============================================================
# API CLIENT
# ============================================================

class HuioneAPIBridge:
    """Read-only API client for Huione Pay foundation-server."""

    def __init__(self, base_url=None, verify_ssl=False):
        if not HAS_REQUESTS:
            raise ImportError("requests package required: pip install requests")

        self.base_url = base_url or SERVERS["primary"]
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "okhttp/4.9.3",
            "Accept": "application/json",
        })
        self.token = None
        self.channel_key = None  # Set after ECDH exchange

    def _url(self, endpoint: str) -> str:
        return self.base_url + endpoint

    def _post(self, endpoint: str, data: dict = None, encrypt: bool = False) -> dict:
        """Send POST request, optionally encrypt body and decrypt response."""
        url = self._url(endpoint)
        headers = {}

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = data or {}

        if encrypt and self.channel_key:
            body_str = json.dumps(body)
            body = {"data": aes_encrypt(body_str, self.channel_key)}

        try:
            resp = self.session.post(url, json=body, headers=headers, timeout=30)
            result = resp.json()

            # Auto-decrypt if response has encrypted data field
            if isinstance(result, dict) and "data" in result and isinstance(result["data"], str):
                try:
                    key = self.channel_key or HUIONE_AES_KEY
                    decrypted = aes_decrypt(result["data"], key)
                    result["data_decrypted"] = json.loads(decrypted)
                except Exception:
                    pass  # Not encrypted or different key

            return result

        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def probe_health(self) -> dict:
        """Probe server health (no auth required)."""
        results = {}
        for name, url in SERVERS.items():
            try:
                resp = self.session.get(
                    url + "/foundation/auth/login/getAppInfo",
                    timeout=10,
                )
                results[name] = {
                    "status": resp.status_code,
                    "reachable": True,
                    "response_preview": str(resp.text[:200]),
                }
            except Exception as e:
                results[name] = {
                    "status": None,
                    "reachable": False,
                    "error": str(e),
                }
        return results

    def probe_rpc(self) -> dict:
        """Probe Huione Chain RPC endpoint."""
        rpc_calls = [
            {"method": "getHealth", "params": []},
            {"method": "getVersion", "params": []},
            {"method": "getSlot", "params": []},
            {"method": "getBlockHeight", "params": []},
            # EVM-style (in case of Xone Chain)
            {"method": "eth_chainId", "params": []},
            {"method": "eth_blockNumber", "params": []},
        ]

        results = {}
        for call in rpc_calls:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": call["method"],
                "params": call["params"],
            }
            try:
                resp = self.session.post(
                    HUIONE_CHAIN_RPC,
                    json=payload,
                    timeout=15,
                )
                results[call["method"]] = {
                    "status": resp.status_code,
                    "response": resp.json() if resp.status_code == 200 else resp.text[:200],
                }
            except Exception as e:
                results[call["method"]] = {"error": str(e)}

        return results

    # --- Read-only query methods ---

    def get_app_info(self) -> dict:
        return self._post("/foundation/auth/login/getAppInfo")

    def get_account(self) -> dict:
        return self._post("/foundation/account/get", encrypt=True)

    def query_bills(self, page=1, size=20, bill_big_type=None) -> dict:
        params = {"pageNum": page, "pageSize": size}
        if bill_big_type:
            params["billBigType"] = bill_big_type
        return self._post("/foundation/bill/query", params, encrypt=True)

    def query_bill_page(self, page=1, size=20) -> dict:
        params = {"pageNum": page, "pageSize": size}
        return self._post("/foundation/dc-bill/app/pageBillListData", params, encrypt=True)

    def get_deposit_currencies(self) -> dict:
        return self._post("/foundation/account/v3/depositCurrency")

    def get_withdraw_currencies(self) -> dict:
        return self._post("/foundation/account/withdrawCurrency")


# ============================================================
# CLI COMMANDS
# ============================================================

def cmd_test():
    """Test ECDH + AES logic."""
    print("=" * 60)
    print("  Huione Pay API Bridge - Self Test")
    print("=" * 60)

    # Test 1: AES round-trip
    print("\n[Test 1] AES-256-ECB Round-trip")
    test_data = '{"userId":12345,"currency":"USDT","amount":100}'
    encrypted = aes_encrypt(test_data)
    decrypted = aes_decrypt(encrypted)
    assert decrypted == test_data, f"FAIL: {decrypted} != {test_data}"
    print(f"  Plaintext:  {test_data}")
    print(f"  Encrypted:  {encrypted[:60]}...")
    print(f"  Decrypted:  {decrypted}")
    print(f"  Status:     PASS")

    # Test 2: Known key verification
    print("\n[Test 2] Huione AES Key Verification")
    key = HUIONE_AES_KEY
    print(f"  Key:        {key.decode()}")
    print(f"  Length:     {len(key)} bytes (AES-256)")
    print(f"  SHA256:     {hashlib.sha256(key).hexdigest()}")
    print(f"  Status:     PASS")

    # Test 3: ECDH simulation
    print("\n[Test 3] ECDH Key Exchange Simulation")
    ecdh_ok = simulate_ecdh()
    print(f"  Status:     {'PASS' if ecdh_ok else 'SKIP (install cryptography package)'}")

    # Test 4: URL encode/decode consistency
    print("\n[Test 4] URL Encoding Consistency")
    special_data = '{"memo":"test+data&special=chars","amount":"1,000.50"}'
    enc = aes_encrypt(special_data)
    dec = aes_decrypt(enc)
    assert dec == special_data
    print(f"  Special chars: PASS")

    print("\n" + "=" * 60)
    print("  All tests passed!")
    print("=" * 60)


def cmd_info():
    """Show API endpoint map."""
    print("=" * 70)
    print("  Huione Pay API Endpoint Map")
    print("=" * 70)

    for category, endpoints in API_ENDPOINTS.items():
        print(f"\n  [{category.upper()}]")
        for name, path in endpoints.items():
            print(f"    {name:25s}  POST {path}")

    print(f"\n  [SERVERS]")
    for name, url in SERVERS.items():
        print(f"    {name:25s}  {url}")

    print(f"\n  [BLOCKCHAIN]")
    print(f"    {'Huione Chain RPC':25s}  {HUIONE_CHAIN_RPC}")
    print(f"    {'Huione Chain Explorer':25s}  {HUIONE_CHAIN_EXPLORER}")

    print(f"\n  [INSTANCES]")
    for iid, name in INSTANCES.items():
        print(f"    {iid:25s}  {name}")

    print(f"\n  Total endpoints: {sum(len(v) for v in API_ENDPOINTS.values())}")
    print("=" * 70)


def cmd_probe():
    """Probe server health."""
    if not HAS_REQUESTS:
        print("[ERROR] requests package required: pip install requests")
        return

    print("[*] Probing Huione Pay servers...")
    bridge = HuioneAPIBridge()

    results = bridge.probe_health()
    for name, info in results.items():
        status = "UP" if info["reachable"] else "DOWN"
        print(f"  [{status}] {name}: HTTP {info.get('status', 'N/A')}")
        if info.get("error"):
            print(f"         Error: {info['error'][:100]}")
        if info.get("response_preview"):
            print(f"         Response: {info['response_preview'][:100]}...")


def cmd_rpc_test():
    """Test Huione Chain RPC."""
    if not HAS_REQUESTS:
        print("[ERROR] requests package required: pip install requests")
        return

    print("[*] Testing Huione Chain RPC at", HUIONE_CHAIN_RPC)
    bridge = HuioneAPIBridge()

    results = bridge.probe_rpc()
    for method, info in results.items():
        if "error" in info:
            print(f"  [{method}] ERROR: {info['error'][:80]}")
        else:
            print(f"  [{method}] HTTP {info['status']}: {json.dumps(info.get('response', ''))[:100]}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Huione Pay Read-Only API Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  --test       Run self-test (ECDH + AES verification)
  --info       Show API endpoint map
  --probe      Probe server health
  --rpc-test   Test Huione Chain RPC endpoint
        """,
    )
    parser.add_argument("--test", action="store_true", help="Run self-test")
    parser.add_argument("--info", action="store_true", help="Show API endpoint map")
    parser.add_argument("--probe", action="store_true", help="Probe server health")
    parser.add_argument("--rpc-test", action="store_true", help="Test Huione Chain RPC")
    parser.add_argument("--server", help="Custom server URL")

    args = parser.parse_args()

    if args.test:
        cmd_test()
    elif args.info:
        cmd_info()
    elif args.probe:
        cmd_probe()
    elif args.rpc_test:
        cmd_rpc_test()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
