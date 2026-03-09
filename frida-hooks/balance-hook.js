// balance_hook_v7.js - Brute Force Handshake Bypass
// Hook 2 key functions found via Stalker trace, force return values
'use strict';

function findExport(mod, fn) {
    var m = Process.findModuleByName(mod);
    return m ? m.findExportByName(fn) : null;
}
function safeStr(ptr, maxLen) {
    try { if (ptr.isNull()) return null; return maxLen ? ptr.readUtf8String(maxLen) : ptr.readUtf8String(); } catch(e) { return null; }
}

var CFG = {
    DISPLAY_BALANCE: "999888.77",
    REDIRECT_IP: "127.0.0.1",
    REDIRECT_ENABLED: true,
    TARGET_DOMAINS: ["app.hh3721.com", "api.ip.sb", "ipwho.is"],
    SPOOF_UUID: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    UUID_SPOOF_ENABLED: true,
    PROP_SPOOF_ENABLED: true,
    SPOOF_PROPS: {
        "ro.product.model": "Pixel 6", "ro.product.brand": "google",
        "ro.product.device": "oriole", "ro.product.manufacturer": "Google"
    },
    INJECT_PERMISSIONS: true,
    PERM_KEYS: {
        "flutter.permissions.withdraw.wallet": "true",
        "flutter.permissions.transfer": "true",
        "flutter.permissions.deposit": "true",
        "flutter.permissions.deposit.chain": "true",
        "flutter.permissions.withdraw": "true",
        "flutter.permissions.withdraw.bank_card": "true"
    }
};

var CAPTURED = {
    ssl_bypass: { overrides_hs: 0, overrides_wrap: 0, overrides_verify: 0 },
    dns_redirects: 0, balance_modifications: 0, api_responses_captured: 0,
    original_balances: [], servers: [], dns: [], files_opened: 0,
    uuid_spoof_count: 0, prop_spoof_count: 0, perm_inject_count: 0,
    traffic_out: 0, traffic_in: 0, port_redirects: 0
};
var openFds = {};
var tlsFds = {};

// ==========================================
// PHASE 1: BRUTE FORCE SSL BYPASS
// ==========================================

function bypassSSL() {
    var checkCount = 0;
    var timer = setInterval(function() {
        checkCount++;
        var flutter = Process.findModuleByName("libflutter.so");
        if (flutter) {
            clearInterval(timer);
            send("[SSL] libflutter.so @ " + flutter.base + " size=" + flutter.size);
            doSSLBypass(flutter);
        } else if (checkCount >= 40) {
            clearInterval(timer);
        }
    }, 500);
}

function doSSLBypass(flutter) {
    send("[SSL] === Brute Force Handshake Bypass v7 ===");
    var base = flutter.base;

    // 1. Hook Main Handshake function (1094 bytes, 55 BL calls)
    //    From Stalker trace: this function processes TLS after ServerHello
    //    Force return 0 (ssl_verify_ok in BoringSSL)
    var fnHandshake = base.add(0x62e2ac);
    try {
        Interceptor.attach(fnHandshake.or(1), {
            onEnter: function(args) {
                send("[HS] ENTER +62e2ac R0=" + args[0]);
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                send("[HS] LEAVE +62e2ac ret=" + orig + " -> FORCING 0");
                retval.replace(ptr(0));
                CAPTURED.ssl_bypass.overrides_hs++;
            }
        });
        send("[SSL] HOOKED +62e2ac (Main Handshake) -> force ret=0");
    } catch(e) {
        send("[SSL] ERR +62e2ac: " + e);
    }

    // 2. Hook Dart VM Wrapper (102 bytes, indirect calls via R12)
    //    This bridges Dart <-> Native SSL
    //    Force return 1 (success for Dart)
    var fnWrapper = base.add(0x6331d0);
    try {
        Interceptor.attach(fnWrapper.or(1), {
            onEnter: function(args) {
                send("[WRAP] ENTER +6331d0 R0=" + args[0] + " R1=" + args[1]);
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                send("[WRAP] LEAVE +6331d0 ret=" + orig + " -> FORCING 1");
                retval.replace(ptr(1));
                CAPTURED.ssl_bypass.overrides_wrap++;
            }
        });
        send("[SSL] HOOKED +6331d0 (Dart Wrapper) -> force ret=1");
    } catch(e) {
        send("[SSL] ERR +6331d0: " + e);
    }

    // 3. Also hook the new verify candidate from pattern analysis
    //    +2ee4d0: CMP R0,#0 + CMP R0,#2 (ssl_verify_result_t check)
    var fnVerify = base.add(0x2ee4d0);
    try {
        Interceptor.attach(fnVerify.or(1), {
            onEnter: function(args) {
                send("[VERIFY] ENTER +2ee4d0 R0=" + args[0]);
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                send("[VERIFY] LEAVE +2ee4d0 ret=" + orig + " -> FORCING 0");
                retval.replace(ptr(0));
                CAPTURED.ssl_bypass.overrides_verify++;
            }
        });
        send("[SSL] HOOKED +2ee4d0 (Verify candidate) -> force ret=0");
    } catch(e) {
        send("[SSL] ERR +2ee4d0: " + e);
    }

    send("[SSL] All hooks installed. Watching handshake...");
}

bypassSSL();

// ==========================================
// PHASE 2: DNS REDIRECT
// ==========================================
var c_getaddrinfo = findExport("libc.so", "getaddrinfo");
if (c_getaddrinfo) {
    Interceptor.attach(c_getaddrinfo, {
        onEnter: function(args) {
            var host = safeStr(args[0]);
            if (host) {
                if (CAPTURED.dns.indexOf(host) === -1) { CAPTURED.dns.push(host); send("DNS: " + host); }
                if (CFG.REDIRECT_ENABLED) {
                    for (var i = 0; i < CFG.TARGET_DOMAINS.length; i++) {
                        if (host === CFG.TARGET_DOMAINS[i]) {
                            CAPTURED.dns_redirects++;
                            send("DNS_REDIRECT: " + host + " -> " + CFG.REDIRECT_IP);
                            args[0].writeUtf8String(CFG.REDIRECT_IP);
                            break;
                        }
                    }
                }
            }
        }
    });
    send("[OK] getaddrinfo()");
}

// ==========================================
// PHASE 3: CONNECT HOOK
// ==========================================
var c_connect = findExport("libc.so", "connect");
if (c_connect) {
    Interceptor.attach(c_connect, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            try {
                var sa = args[1];
                if (sa.readU16() === 2) {
                    var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                    var ip = sa.add(4).readU8() + "." + sa.add(5).readU8() + "." +
                             sa.add(6).readU8() + "." + sa.add(7).readU8();
                    var entry = ip + ":" + port;
                    if (CAPTURED.servers.indexOf(entry) === -1) { CAPTURED.servers.push(entry); send("CONNECT: " + entry); }
                    if (ip === "127.0.0.1" && port === 443) {
                        sa.add(2).writeU8(0x20);
                        sa.add(3).writeU8(0xFB);
                        CAPTURED.port_redirects++;
                        send("PORT_REDIRECT: fd" + this.fd);
                        this.isMock = true;
                    }
                }
            } catch(e) {}
        },
        onLeave: function(retval) {
            if (this.isMock) tlsFds[this.fd] = true;
        }
    });
    send("[OK] connect()");
}

// ==========================================
// PHASE 4: FILE I/O + TLS MONITOR
// ==========================================
var c_open = findExport("libc.so", "open");
if (c_open) {
    Interceptor.attach(c_open, {
        onEnter: function(args) { this.path = safeStr(args[0]); },
        onLeave: function(retval) {
            var fd = retval.toInt32();
            if (fd >= 0 && this.path) {
                CAPTURED.files_opened++;
                var p = this.path.toLowerCase();
                if (p.indexOf("shared_prefs") !== -1 || p.indexOf("uuid") !== -1 ||
                    p.indexOf("flutter") !== -1 || p.indexOf("huione") !== -1 ||
                    p.indexOf("token") !== -1 || p.indexOf("device") !== -1) {
                    openFds[fd] = this.path;
                }
            }
        }
    });
}

var c_read = findExport("libc.so", "read");
if (c_read) {
    Interceptor.attach(c_read, {
        onEnter: function(args) {
            this.fd = args[0].toInt32(); this.buf = args[1]; this.filePath = openFds[this.fd] || null;
            this.isTls = !!tlsFds[this.fd];
        },
        onLeave: function(retval) {
            var n = retval.toInt32();
            if (this.isTls && n >= 5) {
                try {
                    var ct = this.buf.readU8();
                    if (ct >= 20 && ct <= 23) {
                        var ctNames = {20: "CCS", 21: "Alert", 22: "HS", 23: "AppData"};
                        var label = ctNames[ct] || "ct" + ct;
                        if (ct === 22 && n > 5) {
                            var hsType = this.buf.add(5).readU8();
                            var hsNames = {2: "ServerHello", 11: "Cert", 14: "Done", 20: "Finished"};
                            label = "HS:" + (hsNames[hsType] || hsType);
                        }
                        send("TLS_IN[fd" + this.fd + "]: " + label + " n=" + n);
                    }
                } catch(e) {}
                return;
            }
            if (!this.filePath || n <= 0 || n > 131072) return;
            var data = safeStr(this.buf, n);
            if (!data) return;
            var path = this.filePath.toLowerCase();
            var modified = false, newData = data;

            if (CFG.UUID_SPOOF_ENABLED && path.indexOf("device_uuid") !== -1) {
                var m = data.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                if (m) { newData = data.replace(m[0], CFG.SPOOF_UUID); modified = true; CAPTURED.uuid_spoof_count++; send("UUID_SPOOF: " + m[0] + " -> " + CFG.SPOOF_UUID); }
            }
            if (path.indexOf("fluttersharedpreferences") !== -1 && CFG.INJECT_PERMISSIONS) {
                var me = newData.indexOf("</map>");
                if (me !== -1) {
                    var inj = ""; var ks = Object.keys(CFG.PERM_KEYS);
                    for (var j = 0; j < ks.length; j++) { if (newData.indexOf(ks[j]) === -1) inj += '    <string name="' + ks[j] + '">' + CFG.PERM_KEYS[ks[j]] + '</string>\n'; }
                    if (inj) { newData = newData.substring(0, me) + inj + newData.substring(me); modified = true; CAPTURED.perm_inject_count++; }
                }
            }
            if (data.indexOf("balanceList") !== -1 || data.indexOf('"balance"') !== -1 || data.indexOf("wealth") !== -1) {
                send("BALANCE_DATA: " + data.substring(0, 500));
                CAPTURED.api_responses_captured++;
                var bps = [/("balance"\s*:\s*")([0-9.]+)(")/g, /("availableAmount"\s*:\s*")([0-9.]+)(")/g,
                           /("totalWealth"\s*:\s*")([0-9.]+)(")/g, /("amount"\s*:\s*")([0-9.]+)(")/g];
                for (var bi = 0; bi < bps.length; bi++) {
                    if (newData.match(bps[bi])) {
                        newData = newData.replace(bps[bi], function(_, pre, val, post) {
                            CAPTURED.original_balances.push(val); CAPTURED.balance_modifications++;
                            return pre + CFG.DISPLAY_BALANCE + post;
                        }); modified = true;
                    }
                }
            }
            if (modified && newData !== data) {
                try { this.buf.writeUtf8String(newData); retval.replace(newData.length);
                    send("MODIFIED: " + this.filePath + " (" + n + "B -> " + newData.length + "B)");
                } catch(e) {}
            }
        }
    });
    send("[OK] read()");
}

var c_write = findExport("libc.so", "write");
if (c_write) { Interceptor.attach(c_write, { onEnter: function(args) {
    var fd = args[0].toInt32(); var len = args[2].toInt32();
    if (tlsFds[fd] && len >= 5) {
        try {
            var ct = args[1].readU8();
            if (ct === 22 && len > 5) {
                var hsType = args[1].add(5).readU8();
                send("TLS_OUT[fd" + fd + "]: HS:type" + hsType + " len=" + len);
            }
            if (ct === 21) send("TLS_ALERT[fd" + fd + "]: code=" + ((len>=7)?args[1].add(6).readU8():-1));
            if (ct === 23) send("TLS_APPDATA_OUT[fd" + fd + "]: len=" + len);
        } catch(e) {}
    }
    if (openFds[fd]) {
        if (len > 0 && len < 131072) { var d = safeStr(args[1], len); if (d) {
            if (CFG.UUID_SPOOF_ENABLED && openFds[fd].toLowerCase().indexOf("device_uuid") !== -1) {
                var m = d.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                if (m && m[0] !== CFG.SPOOF_UUID) try { args[1].writeUtf8String(d.replace(m[0], CFG.SPOOF_UUID)); CAPTURED.uuid_spoof_count++; } catch(e) {}
            }
        } }
    }
} }); }

var prop_get = findExport("libc.so", "__system_property_get");
if (prop_get) { Interceptor.attach(prop_get, {
    onEnter: function(args) { this.n = safeStr(args[0]); this.v = args[1]; },
    onLeave: function(r) { if (this.n && CFG.PROP_SPOOF_ENABLED && CFG.SPOOF_PROPS[this.n]) try { this.v.writeUtf8String(CFG.SPOOF_PROPS[this.n]); CAPTURED.prop_spoof_count++; } catch(e) {} }
}); }

var c_close = findExport("libc.so", "close");
if (c_close) { Interceptor.attach(c_close, { onEnter: function(args) {
    var fd = args[0].toInt32();
    if (openFds[fd]) delete openFds[fd];
    if (tlsFds[fd]) { send("TLS_CLOSE: fd" + fd); delete tlsFds[fd]; }
} }); }

rpc.exports = {
    dump: function() { return JSON.stringify(CAPTURED, null, 2); },
    setBalance: function(b) { CFG.DISPLAY_BALANCE = b; }
};

send("=== BALANCE HOOK v7 (Brute Force Handshake) ===");
send("Handshake +62e2ac -> force ret=0");
send("Wrapper   +6331d0 -> force ret=1");
send("Verify    +2ee4d0 -> force ret=0");

setInterval(function() {
    send("STATUS: hs=" + CAPTURED.ssl_bypass.overrides_hs +
         " wrap=" + CAPTURED.ssl_bypass.overrides_wrap +
         " verify=" + CAPTURED.ssl_bypass.overrides_verify +
         " bal=" + CAPTURED.balance_modifications +
         " dns=" + CAPTURED.dns_redirects +
         " port=" + CAPTURED.port_redirects);
}, 15000);
