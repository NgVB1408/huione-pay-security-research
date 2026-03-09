#!/usr/bin/env python3
"""
aes_decryptor.py - Decrypt/Encrypt Huione Pay SDK data
=======================================================
Implement chinh xac quy trinh tu AbstractC0229a.java:m531q (line 1015-1036):

  Input -> URL decode -> Base64 decode -> AES/ECB/PKCS7Padding decrypt
  Key:   "keyhead_project_xhui_one_keytail" (32 bytes)

Encrypt (reverse):
  Input -> AES/ECB/PKCS7Padding encrypt -> Base64 encode -> URL encode

Usage:
  python aes_decryptor.py "encoded_data"
  python aes_decryptor.py --file data.txt
  python aes_decryptor.py --encrypt "plaintext"
  python aes_decryptor.py --encrypt --file plain.txt
  echo "encoded" | python aes_decryptor.py --stdin
"""

import argparse
import sys
import base64
from urllib.parse import quote, unquote

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    print("[ERROR] pycryptodome is required. Install with: pip install pycryptodome", file=sys.stderr)
    sys.exit(1)

# ============================================================
# CONSTANTS - From AbstractC0229a.java:1018
# ============================================================

HUIONE_AES_KEY = b"keyhead_project_xhui_one_keytail"  # 32 bytes = AES-256
AES_MODE = AES.MODE_ECB
BLOCK_SIZE = 16  # AES block size


# ============================================================
# CORE FUNCTIONS
# ============================================================

def decrypt_sdk(encoded_data: str, key: bytes = HUIONE_AES_KEY) -> str:
    """
    Decrypt Huione SDK data.
    Mirrors AbstractC0229a.m531q() exactly:
      1. URL decode
      2. Base64 decode
      3. AES/ECB/PKCS7 decrypt
    """
    # Step 1: URL decode (java.net.URLDecoder.decode)
    url_decoded = unquote(encoded_data.strip())

    # Step 2: Base64 decode
    try:
        ciphertext = base64.b64decode(url_decoded)
    except Exception as e:
        raise ValueError(f"Base64 decode failed: {e}")

    # Step 3: Prepare AES key (32-byte array, copy key bytes)
    key_bytes = bytearray(32)
    key_data = key[:32]
    key_bytes[:len(key_data)] = key_data

    # Step 4: AES/ECB/PKCS7Padding decrypt
    cipher = AES.new(bytes(key_bytes), AES_MODE)
    try:
        plaintext_padded = cipher.decrypt(ciphertext)
        plaintext = unpad(plaintext_padded, BLOCK_SIZE)
    except ValueError as e:
        # Try without unpadding (some data may not be PKCS7 padded)
        plaintext = cipher.decrypt(ciphertext).rstrip(b'\x00')

    return plaintext.decode("utf-8", errors="replace").strip()


def encrypt_sdk(plaintext: str, key: bytes = HUIONE_AES_KEY) -> str:
    """
    Encrypt data in Huione SDK format (reverse of decrypt).
      1. AES/ECB/PKCS7 encrypt
      2. Base64 encode
      3. URL encode
    """
    # Step 1: Prepare AES key
    key_bytes = bytearray(32)
    key_data = key[:32]
    key_bytes[:len(key_data)] = key_data

    # Step 2: AES/ECB/PKCS7Padding encrypt
    cipher = AES.new(bytes(key_bytes), AES_MODE)
    padded = pad(plaintext.encode("utf-8"), BLOCK_SIZE)
    ciphertext = cipher.encrypt(padded)

    # Step 3: Base64 encode
    b64_encoded = base64.b64encode(ciphertext).decode("ascii")

    # Step 4: URL encode
    url_encoded = quote(b64_encoded, safe="")

    return url_encoded


def decrypt_raw_aes(ciphertext_hex: str, key: bytes = HUIONE_AES_KEY) -> str:
    """Decrypt raw hex ciphertext (for debugging)."""
    ciphertext = bytes.fromhex(ciphertext_hex)
    key_bytes = bytearray(32)
    key_bytes[:len(key)] = key
    cipher = AES.new(bytes(key_bytes), AES_MODE)
    plaintext = unpad(cipher.decrypt(ciphertext), BLOCK_SIZE)
    return plaintext.decode("utf-8", errors="replace")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Huione Pay AES-256-ECB Decryptor/Encryptor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decrypt URL-encoded+Base64+AES data:
  python aes_decryptor.py "NjRVZ0..."

  # Decrypt from file:
  python aes_decryptor.py --file encrypted_data.txt

  # Encrypt plaintext (for testing):
  python aes_decryptor.py --encrypt "hello world"

  # Round-trip test:
  python aes_decryptor.py --encrypt "test" | python aes_decryptor.py --stdin

  # Use custom key:
  python aes_decryptor.py --key "my_custom_32byte_key_here_padded" "data"

  # Decrypt raw hex AES ciphertext:
  python aes_decryptor.py --hex "aabbccdd..."
        """,
    )
    parser.add_argument("data", nargs="?", help="Data to decrypt/encrypt")
    parser.add_argument("--file", "-f", help="Read input from file")
    parser.add_argument("--stdin", action="store_true", help="Read input from stdin")
    parser.add_argument("--encrypt", "-e", action="store_true", help="Encrypt mode (default: decrypt)")
    parser.add_argument("--key", "-k", help="Custom AES key (default: Huione hardcoded key)")
    parser.add_argument("--hex", action="store_true", help="Input is raw hex ciphertext")
    parser.add_argument("--output", "-o", help="Write output to file")
    parser.add_argument("--batch", "-b", action="store_true", help="Batch mode: one item per line")

    args = parser.parse_args()

    # Determine key
    key = args.key.encode("utf-8") if args.key else HUIONE_AES_KEY

    # Get input data
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            input_data = f.read()
    elif args.stdin:
        input_data = sys.stdin.read()
    elif args.data:
        input_data = args.data
    else:
        parser.print_help()
        sys.exit(1)

    # Process
    results = []
    if args.batch:
        lines = [l.strip() for l in input_data.strip().splitlines() if l.strip()]
    else:
        lines = [input_data.strip()]

    for i, line in enumerate(lines):
        try:
            if args.encrypt:
                result = encrypt_sdk(line, key)
                results.append(result)
            elif args.hex:
                result = decrypt_raw_aes(line, key)
                results.append(result)
            else:
                result = decrypt_sdk(line, key)
                results.append(result)
        except Exception as e:
            error_msg = f"[ERROR line {i + 1}] {e}"
            print(error_msg, file=sys.stderr)
            results.append(error_msg)

    # Output
    output = "\n".join(results)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[*] Output written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
