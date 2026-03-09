#!/usr/bin/env python3
"""
Huione Pay — Live Infrastructure Proof Generator
Captures timestamped evidence that servers are LIVE and RESPONDING.
Output: JSON file with all responses + timestamps for forensic use.

Usage: python live_infrastructure_proof.py
Output: infrastructure_evidence_<timestamp>.json
"""

import json
import time
import datetime
import hashlib
import requests
import urllib3
urllib3.disable_warnings()

EVIDENCE = {
    "report_metadata": {
        "title": "Huione Pay Infrastructure — Live Evidence Capture",
        "generated_utc": None,
        "tool": "live_infrastructure_proof.py",
        "purpose": "Demonstrate that Huione Pay infrastructure is active and responding"
    },
    "probes": []
}

def probe(name, url, method="GET", data=None, headers=None, timeout=15):
    """Send a request and record full response metadata."""
    entry = {
        "name": name,
        "url": url,
        "method": method,
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "status": None,
        "response_time_ms": None,
        "response_body": None,
        "response_headers": {},
        "remote_ip": None,
        "error": None,
        "sha256_response": None
    }

    try:
        if headers is None:
            headers = {"Content-Type": "application/json"}

        start = time.time()
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        else:
            r = requests.post(url, data=json.dumps(data) if isinstance(data, dict) else data,
                            headers=headers, timeout=timeout, verify=False)
        elapsed = (time.time() - start) * 1000

        entry["status"] = r.status_code
        entry["response_time_ms"] = round(elapsed, 1)
        entry["response_headers"] = dict(r.headers)

        body = r.text[:5000]
        entry["response_body"] = body
        entry["sha256_response"] = hashlib.sha256(r.content).hexdigest()

        try:
            entry["response_json"] = r.json()
        except:
            pass

        print(f"  [{r.status_code}] {name} ({elapsed:.0f}ms)")

    except Exception as e:
        entry["error"] = str(e)
        print(f"  [ERR] {name}: {e}")

    EVIDENCE["probes"].append(entry)
    return entry

def main():
    print("=" * 60)
    print("Huione Pay — Live Infrastructure Evidence Capture")
    print("=" * 60)

    EVIDENCE["report_metadata"]["generated_utc"] = \
        datetime.datetime.utcnow().isoformat() + "Z"

    # 1. S3 Server Discovery
    print("\n[1] S3 Server Configuration (datadogips)")
    probe("S3 IP Config",
          "https://datadogips.s3.ap-southeast-1.amazonaws.com/ip.json")

    # 2. Primary API Server
    print("\n[2] Primary API Server")
    probe("Primary API",
          "https://app.hh3721.com/app/foundation-server/foundation/common/nations",
          method="POST", data={})

    # 3. Public endpoints (no auth)
    print("\n[3] Public Endpoints")
    probe("Customer Service",
          "https://app.hh3721.com/app/foundation-server/foundation/common/customerServices",
          method="POST", data={})

    probe("Skip Links",
          "https://app.hh3721.com/app/foundation-server/foundation/common/skipLink",
          method="POST", data={})

    # 4. CAPTCHA endpoint (expected 404 — proves it's disabled)
    print("\n[4] CAPTCHA Endpoint (expected: disabled)")
    probe("CAPTCHA Check",
          "https://app.hh3721.com/app/foundation-server/foundation/user/checkManMachine",
          method="POST", data={"type": "login"})

    # 5. Huione Chain RPC
    print("\n[5] Huione Chain Blockchain RPC")
    probe("RPC getVersion",
          "https://rpc.huione.org",
          method="POST",
          data={"jsonrpc": "2.0", "id": 1, "method": "getVersion", "params": []})

    probe("RPC getEpochInfo",
          "https://rpc.huione.org",
          method="POST",
          data={"jsonrpc": "2.0", "id": 1, "method": "getEpochInfo", "params": []})

    probe("RPC getSlot",
          "https://rpc.huione.org",
          method="POST",
          data={"jsonrpc": "2.0", "id": 1, "method": "getSlot", "params": []})

    # 6. BSC Phishing Contract — C2 URL
    print("\n[6] BSC Phishing Contract (C2 URL)")
    probe("BSC Contract C2",
          "https://bsc-dataseed.binance.org",
          method="POST",
          data={
              "jsonrpc": "2.0", "id": 1, "method": "eth_call",
              "params": [{
                  "to": "0xe9d5f645f79fa60fca82b4e1d35832e43370feb0",
                  "data": "0x20965255"
              }, "latest"]
          })

    # 7. Geolocation services (hardcoded in app)
    print("\n[7] Geolocation Services (hardcoded)")
    probe("ipwho.is", "https://ipwho.is/")
    probe("api.ip.sb", "https://api.ip.sb/geoip/")
    probe("ipapi.co", "https://ipapi.co/json/")

    # 8. Direct backend IPs
    print("\n[8] Direct Backend IPs (CDN/WAF bypass)")
    probe("Direct IP 8.217.236.122",
          "https://8.217.236.122:19003/app/foundation-server/foundation/common/nations",
          method="POST", data={})

    # 9. Cancel account page
    print("\n[9] Account Cancellation Page")
    probe("Cancel Account", "https://cancelaccount-h5.oykqk.com")

    # Save evidence
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"infrastructure_evidence_{ts}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(EVIDENCE, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 60}")
    print(f"Evidence saved: {filename}")
    print(f"Total probes: {len(EVIDENCE['probes'])}")
    success = sum(1 for p in EVIDENCE["probes"] if p["status"] and p["status"] < 500)
    print(f"Successful: {success}/{len(EVIDENCE['probes'])}")
    print(f"SHA-256 of evidence file: ", end="")
    with open(filename, 'rb') as f:
        print(hashlib.sha256(f.read()).hexdigest())
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
