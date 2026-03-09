#!/usr/bin/env python3
"""
Huione Pay Security Research — Infrastructure Monitor
======================================================
Read-only monitoring dashboard for tracking the live status of
Huione Pay infrastructure endpoints identified during research.

Features:
  - Infrastructure endpoint health checks (read-only probes)
  - Blockchain RPC monitoring (Huione Chain + BSC)
  - AES decrypt utility for captured traffic analysis
  - Vulnerability reference panel

This tool performs read-only network probes only.
No authentication, account manipulation, or transaction signing.

Usage:
  python research-dashboard.py
"""

import json
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
import base64
import os
from urllib.parse import unquote

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ─────────────────────────────────────────────
# INFRASTRUCTURE ENDPOINTS (read-only probes)
# ─────────────────────────────────────────────
ENDPOINTS = [
    {"name": "S3 IP Config",         "url": "https://datadogips.s3.ap-southeast-1.amazonaws.com/ip.json",          "method": "GET"},
    {"name": "Primary API",          "url": "https://app.hh3721.com/app/foundation-server/foundation/common/nations", "method": "POST"},
    {"name": "Huione Chain RPC",     "url": "https://rpc.huione.org",                                               "method": "POST",
     "body": {"jsonrpc": "2.0", "id": 1, "method": "getVersion", "params": []}},
    {"name": "BSC RPC",              "url": "https://bsc-dataseed.binance.org",                                     "method": "POST",
     "body": {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}},
    {"name": "CAPTCHA Check",        "url": "https://app.hh3721.com/app/foundation-server/foundation/user/checkManMachine", "method": "POST"},
]

VULN_LIST = [
    ("CRIT-001", "Hardcoded AES-256-ECB Key",          "Critical", "9.8"),
    ("CRIT-002", "SSL Pinning — 4 Layers Bypassed",    "Critical", "8.8"),
    ("CRIT-003", "OTP Bypass (No Rate Limit)",          "Critical", "9.3"),
    ("CRIT-004", "Multi-Sig Race Condition",            "Critical", "9.0"),
    ("CRIT-005", "Withdraw Address IDOR",               "Critical", "9.1"),
    ("HIGH-001", "Device Identity Spoofing",            "High",     "7.3"),
    ("HIGH-002", "Client-Side Permission Model",        "High",     "8.1"),
    ("HIGH-003", "JWT Token Not Invalidated on Logout", "High",     "7.5"),
    ("HIGH-004", "CAPTCHA Disabled on Auth Endpoint",   "High",     "7.2"),
    ("MED-001",  "Blockchain C2 URL Storage",           "Medium",   "8.1"),
    ("MED-002",  "S3 Bucket — IP Config Exposure",      "Medium",   "7.8"),
    ("MED-003",  "Direct Backend IP Accessible",        "Medium",   "7.5"),
    ("MED-004",  "MQTT Broker Unauthenticated",         "Medium",   "6.8"),
]


class ResearchDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Huione Pay Security Research — Infrastructure Monitor")
        self.root.geometry("1000x680")
        self.root.configure(bg="#0f1117")
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background="#0f1117", borderwidth=0)
        style.configure("TNotebook.Tab",    background="#1a1d27", foreground="#a0a8c0",
                         padding=[12, 6],  font=("Consolas", 9, "bold"))
        style.map("TNotebook.Tab",          background=[("selected", "#2a2d3e")],
                                            foreground=[("selected", "#00d4ff")])
        style.configure("TFrame",           background="#0f1117")
        style.configure("TLabel",           background="#0f1117", foreground="#c0c8e0", font=("Consolas", 9))
        style.configure("Treeview",         background="#1a1d27", foreground="#c0c8e0",
                         fieldbackground="#1a1d27", font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#2a2d3e", foreground="#00d4ff",
                         font=("Consolas", 9, "bold"))

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self._tab_infra(nb)
        self._tab_vulns(nb)
        self._tab_aes(nb)

    # ── Tab 1: Infrastructure Monitor ──────────────────────────────
    def _tab_infra(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Infrastructure Monitor  ")

        hdr = tk.Label(f, text="Read-only infrastructure probe — no authentication used",
                       bg="#0f1117", fg="#ffaa00", font=("Consolas", 9))
        hdr.pack(pady=(8, 2))

        cols = ("Endpoint", "Status", "Response Time", "Last Check")
        self.infra_tree = ttk.Treeview(f, columns=cols, show="headings", height=8)
        for c in cols:
            self.infra_tree.heading(c, text=c)
        self.infra_tree.column("Endpoint",      width=220)
        self.infra_tree.column("Status",        width=100, anchor="center")
        self.infra_tree.column("Response Time", width=120, anchor="center")
        self.infra_tree.column("Last Check",    width=160, anchor="center")
        self.infra_tree.pack(fill="x", padx=10, pady=6)

        self.infra_tree.tag_configure("ok",    foreground="#00ff88")
        self.infra_tree.tag_configure("warn",  foreground="#ffaa00")
        self.infra_tree.tag_configure("error", foreground="#ff4444")

        for ep in ENDPOINTS:
            self.infra_tree.insert("", "end", iid=ep["name"],
                                   values=(ep["name"], "—", "—", "—"), tags=("warn",))

        btn_frame = tk.Frame(f, bg="#0f1117")
        btn_frame.pack(pady=4)
        tk.Button(btn_frame, text="Run Probe", command=self._run_probe,
                  bg="#1e3a5f", fg="#00d4ff", font=("Consolas", 10, "bold"),
                  relief="flat", padx=20, pady=6).pack(side="left", padx=8)

        self.infra_log = scrolledtext.ScrolledText(f, height=12, bg="#0a0c14", fg="#80c8ff",
                                                    font=("Consolas", 8), state="disabled")
        self.infra_log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    def _run_probe(self):
        if not HAS_REQUESTS:
            messagebox.showerror("Missing Dependency", "pip install requests")
            return
        threading.Thread(target=self._probe_thread, daemon=True).start()

    def _probe_thread(self):
        self._log_infra("=== Infrastructure Probe Started ===")
        for ep in ENDPOINTS:
            try:
                t0 = time.time()
                hdrs = {"Content-Type": "application/json"}
                if ep["method"] == "GET":
                    r = requests.get(ep["url"], headers=hdrs, timeout=10, verify=False)
                else:
                    body = ep.get("body", {})
                    r = requests.post(ep["url"], json=body, headers=hdrs, timeout=10, verify=False)
                ms = int((time.time() - t0) * 1000)
                tag = "ok" if r.status_code < 400 else "warn"
                status = f"HTTP {r.status_code}"
            except Exception as e:
                ms = 0
                tag = "error"
                status = f"ERROR"
                self._log_infra(f"  [{ep['name']}] {e}")

            ts = datetime.now().strftime("%H:%M:%S")
            self.infra_tree.item(ep["name"], values=(ep["name"], status, f"{ms} ms", ts), tags=(tag,))
            self._log_infra(f"  [{ep['name']}] {status} — {ms}ms")

        self._log_infra("=== Probe Complete ===\n")

    def _log_infra(self, msg):
        def _do():
            self.infra_log.config(state="normal")
            self.infra_log.insert("end", f"{msg}\n")
            self.infra_log.see("end")
            self.infra_log.config(state="disabled")
        self.root.after(0, _do)

    # ── Tab 2: Vulnerability Reference ────────────────────────────
    def _tab_vulns(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Vulnerability Reference  ")

        tk.Label(f, text="18 Confirmed Vulnerabilities — Huione Pay (com.huione.pay)",
                 bg="#0f1117", fg="#00d4ff", font=("Consolas", 10, "bold")).pack(pady=8)

        cols = ("ID", "Finding", "Severity", "CVSS")
        tree = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID",       width=100)
        tree.column("Finding",  width=420)
        tree.column("Severity", width=100, anchor="center")
        tree.column("CVSS",     width=80,  anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=6)

        tree.tag_configure("Critical", foreground="#ff4444")
        tree.tag_configure("High",     foreground="#ffaa00")
        tree.tag_configure("Medium",   foreground="#ffdd44")

        for row in VULN_LIST:
            tree.insert("", "end", values=row, tags=(row[2],))

    # ── Tab 3: AES Decrypt Utility ────────────────────────────────
    def _tab_aes(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  AES Decrypt Utility  ")

        tk.Label(f, text="AES-256-ECB Decrypt — Captured API Traffic",
                 bg="#0f1117", fg="#00d4ff", font=("Consolas", 10, "bold")).pack(pady=8)

        tk.Label(f, text="Key Source: Set HUIONE_AES_KEY environment variable",
                 bg="#0f1117", fg="#ffaa00", font=("Consolas", 8)).pack()

        inp_frame = tk.Frame(f, bg="#0f1117")
        inp_frame.pack(fill="x", padx=10, pady=6)
        tk.Label(inp_frame, text="Encrypted (Base64+URLenc):", bg="#0f1117", fg="#a0a8c0").pack(anchor="w")
        self.aes_input = tk.Text(inp_frame, height=4, bg="#1a1d27", fg="#c0c8e0",
                                 font=("Consolas", 9), insertbackground="#00d4ff")
        self.aes_input.pack(fill="x")

        tk.Button(f, text="Decrypt", command=self._do_decrypt,
                  bg="#1e3a5f", fg="#00d4ff", font=("Consolas", 10, "bold"),
                  relief="flat", padx=20, pady=6).pack(pady=6)

        out_frame = tk.Frame(f, bg="#0f1117")
        out_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        tk.Label(out_frame, text="Decrypted:", bg="#0f1117", fg="#a0a8c0").pack(anchor="w")
        self.aes_output = scrolledtext.ScrolledText(out_frame, height=8, bg="#0a0c14",
                                                     fg="#00ff88", font=("Consolas", 9))
        self.aes_output.pack(fill="both", expand=True)

    def _do_decrypt(self):
        if not HAS_CRYPTO:
            messagebox.showerror("Missing Dependency", "pip install pycryptodome")
            return
        key_str = os.environ.get("HUIONE_AES_KEY", "")
        if not key_str:
            messagebox.showerror("No Key", "Set HUIONE_AES_KEY environment variable first.")
            return
        key = key_str.encode()[:32].ljust(32, b'\x00')
        data = self.aes_input.get("1.0", "end").strip()
        try:
            url_dec = unquote(data)
            ct = base64.b64decode(url_dec)
            cipher = AES.new(key, AES.MODE_ECB)
            pt = unpad(cipher.decrypt(ct), 16)
            result = pt.decode("utf-8", errors="replace")
        except Exception as e:
            result = f"[ERROR] {e}"
        self.aes_output.delete("1.0", "end")
        self.aes_output.insert("end", result)


def main():
    root = tk.Tk()
    app = ResearchDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
