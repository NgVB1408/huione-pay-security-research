// ssl_bypass_v8.js - Refined BoringSSL SSL Bypass
// Smart return values based on BoringSSL semantics
// Key fix: +0x62e2ac returns 1 (success) not 0 (error)
// Usage: frida -H 127.0.0.1:27042 -n com.huione.pay -l ssl_bypass_v8.js
'use strict';

function findExport(mod, fn) {
    var m = Process.findModuleByName(mod);
    return m ? m.findExportByName(fn) : null;
}

var STATS = {
    verify_patched: 0,
    handshake_patched: 0,
    wrapper_patched: 0,
    verify_passthrough: 0,
    handshake_passthrough: 0,
    wrapper_passthrough: 0,
    tls_alerts: 0,
    tls_handshakes: 0,
    tls_appdata: 0
};

// ==========================================
// PHASE 1: REFINED SSL BYPASS
// ==========================================
function waitForFlutter() {
    var checkCount = 0;
    var timer = setInterval(function() {
        checkCount++;
        var flutter = Process.findModuleByName("libflutter.so");
        if (flutter) {
            clearInterval(timer);
            send("[SSL] libflutter.so @ " + flutter.base + " size=0x" + flutter.size.toString(16));
            installBypass(flutter);
        } else if (checkCount >= 60) {
            clearInterval(timer);
            send("[SSL] TIMEOUT: libflutter.so not found");
        }
    }, 500);
}

function installBypass(flutter) {
    var base = flutter.base;
    send("[SSL] === Refined BoringSSL Bypass v8 ===");

    // =============================================
    // HOOK ORDER MATTERS: verify first, then handshake
    // verify runs inside handshake, so hook it first
    // =============================================

    // 1. +0x2ee4d0 - ssl_verify_peer_cert (CMP R0,#0 / CMP R0,#2)
    // Returns ssl_verify_result_t:
    //   0 = ssl_verify_ok (certificate valid)
    //   1 = ssl_verify_invalid
    //   2 = ssl_verify_retry (async)
    // Strategy: Force 0 (ssl_verify_ok) only when verify fails
    try {
        Interceptor.attach(base.add(0x2ee4d0).or(1), {
            onEnter: function(args) {
                this.ssl = args[0]; // SSL* struct
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                if (orig === 0) {
                    // Already OK, don't touch
                    STATS.verify_passthrough++;
                } else {
                    // Verify failed (1=invalid) or retry (2) → force OK
                    send("[SSL] verify +2ee4d0: ret=" + orig + " -> 0 (ssl_verify_ok)");
                    retval.replace(ptr(0));
                    STATS.verify_patched++;
                }
            }
        });
        send("[SSL] HOOKED +0x2ee4d0 (ssl_verify_peer_cert) -> force ret=0 on failure");
    } catch(e) {
        send("[SSL] ERR +0x2ee4d0: " + e);
        // Fallback: try memory patch
        tryMemoryPatch(base);
    }

    // 2. +0x62e2ac - Main Handshake State Machine (1094 bytes, 55 BL calls)
    // Returns int:
    //   1 = success (handshake complete/progressing)
    //   0 = error
    //  -1 = SSL_ERROR_WANT_READ/WRITE (need more data)
    // Strategy: Force 1 (success) only on error (ret=0), let -1 pass through
    try {
        Interceptor.attach(base.add(0x62e2ac).or(1), {
            onEnter: function(args) {
                this.ssl = args[0];
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                if (orig === 1) {
                    // Success, don't touch
                    STATS.handshake_passthrough++;
                } else if (orig === -1) {
                    // Want read/write - this is normal async behavior, don't touch
                    STATS.handshake_passthrough++;
                } else {
                    // Error (0 or other) → force success
                    send("[SSL] handshake +62e2ac: ret=" + orig + " -> 1 (success)");
                    retval.replace(ptr(1));
                    STATS.handshake_patched++;
                }
            }
        });
        send("[SSL] HOOKED +0x62e2ac (handshake state machine) -> force ret=1 on error");
    } catch(e) {
        send("[SSL] ERR +0x62e2ac: " + e);
    }

    // 3. +0x6331d0 - Dart VM Wrapper (102 bytes, indirect R12 calls)
    // Bridge between Dart SecurityContext and native BoringSSL
    // Returns: 1=OK, 0=fail (Dart convention)
    // Strategy: Force 1 only when it returns 0
    try {
        Interceptor.attach(base.add(0x6331d0).or(1), {
            onEnter: function(args) {
                this.r12 = this.context.r12;
            },
            onLeave: function(retval) {
                var orig = retval.toInt32();
                if (orig === 1) {
                    STATS.wrapper_passthrough++;
                } else {
                    send("[SSL] wrapper +6331d0: ret=" + orig + " -> 1 (Dart success)");
                    retval.replace(ptr(1));
                    STATS.wrapper_patched++;
                }
            }
        });
        send("[SSL] HOOKED +0x6331d0 (Dart wrapper) -> force ret=1 on failure");
    } catch(e) {
        send("[SSL] ERR +0x6331d0: " + e);
    }

    send("[SSL] All 3 hooks installed. Bypass active.");
}

// ==========================================
// FALLBACK: MEMORY PATCH (if Interceptor fails)
// ==========================================
function tryMemoryPatch(base) {
    send("[SSL] Attempting memory patch fallback for +0x2ee4d0...");
    try {
        // Read original bytes first
        var addr = base.add(0x2ee4d0).or(1);
        var origBytes = addr.readByteArray(8);
        send("[SSL] Original bytes at +0x2ee4d0:", origBytes);

        // Patch: MOV R0, #0; BX LR (force return 0 immediately)
        // Thumb2: 00 20 (MOV R0, #0) + 70 47 (BX LR)
        Memory.patchCode(base.add(0x2ee4d0).or(1), 4, function(code) {
            var w = new ThumbWriter(code);
            w.putMovRegU8('r0', 0);   // MOV R0, #0 (ssl_verify_ok)
            w.putBxReg('lr');          // BX LR (return immediately)
            w.flush();
        });
        send("[SSL] PATCHED +0x2ee4d0: MOV R0,#0; BX LR (always ssl_verify_ok)");
    } catch(e) {
        send("[SSL] PATCH ERR: " + e);
    }
}

// ==========================================
// TLS RECORD MONITOR
// ==========================================
var tlsFds = {};

var c_connect = findExport("libc.so", "connect");
if (c_connect) {
    Interceptor.attach(c_connect, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            try {
                var sa = args[1];
                if (sa.readU16() === 2) {
                    var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                    if (port === 443 || port === 8443) {
                        var ip = sa.add(4).readU8() + "." + sa.add(5).readU8() + "." +
                                 sa.add(6).readU8() + "." + sa.add(7).readU8();
                        send("[NET] TLS connect fd" + this.fd + " -> " + ip + ":" + port);
                        this.isTls = true;
                    }
                }
            } catch(e) {}
        },
        onLeave: function(retval) {
            if (this.isTls) tlsFds[this.fd] = true;
        }
    });
}

var c_read = findExport("libc.so", "read");
if (c_read) {
    Interceptor.attach(c_read, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf = args[1];
            this.isTls = !!tlsFds[this.fd];
        },
        onLeave: function(retval) {
            if (!this.isTls) return;
            var n = retval.toInt32();
            if (n < 5) return;
            try {
                var ct = this.buf.readU8();
                if (ct === 22) {
                    STATS.tls_handshakes++;
                    if (n > 5) {
                        var hsType = this.buf.add(5).readU8();
                        var hsNames = {2: "ServerHello", 11: "Cert", 14: "Done", 20: "Finished"};
                        send("[TLS] IN HS:" + (hsNames[hsType] || hsType) + " (" + n + "B)");
                    }
                } else if (ct === 21) {
                    STATS.tls_alerts++;
                    if (n >= 7) {
                        var desc = this.buf.add(6).readU8();
                        var alertNames = {
                            40: "handshake_failure", 42: "bad_certificate",
                            43: "unsupported_cert", 44: "cert_revoked",
                            45: "cert_expired", 46: "cert_unknown",
                            48: "unknown_ca", 80: "internal_error"
                        };
                        send("[TLS] ALERT: " + (alertNames[desc] || "code_" + desc) + " *** CHECK THIS ***");
                    }
                } else if (ct === 23) {
                    STATS.tls_appdata++;
                }
            } catch(e) {}
        }
    });
}

var c_close = findExport("libc.so", "close");
if (c_close) {
    Interceptor.attach(c_close, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            if (tlsFds[fd]) {
                send("[NET] TLS fd" + fd + " closed");
                delete tlsFds[fd];
            }
        }
    });
}

// ==========================================
// RPC & STATUS
// ==========================================
rpc.exports = {
    dump: function() { return JSON.stringify(STATS, null, 2); },
    stats: function() { return STATS; }
};

waitForFlutter();

send("=== SSL BYPASS v8 - REFINED ===");
send("Return Value Strategy:");
send("  +0x2ee4d0 (verify)    -> force 0 (ssl_verify_ok) on failure");
send("  +0x62e2ac (handshake) -> force 1 (success) on error, pass -1");
send("  +0x6331d0 (wrapper)   -> force 1 (Dart OK) on failure");
send("Key fix: handshake returns 1 not 0 (v7 bug)");

setInterval(function() {
    send("[STATUS] patched: v=" + STATS.verify_patched +
         " hs=" + STATS.handshake_patched +
         " w=" + STATS.wrapper_patched +
         " | pass: v=" + STATS.verify_passthrough +
         " hs=" + STATS.handshake_passthrough +
         " w=" + STATS.wrapper_passthrough +
         " | tls: hs=" + STATS.tls_handshakes +
         " alert=" + STATS.tls_alerts +
         " data=" + STATS.tls_appdata);
}, 15000);
