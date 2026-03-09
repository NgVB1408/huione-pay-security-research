// native_hook_full.js - Full native interception for Huione Pay
// Works without Java bridge - pure native hooks
'use strict';

function findExport(mod, fn) {
    var m = Process.findModuleByName(mod);
    return m ? m.findExportByName(fn) : null;
}

function safeStr(ptr, maxLen) {
    try {
        if (ptr.isNull()) return null;
        return maxLen ? ptr.readUtf8String(maxLen) : ptr.readUtf8String();
    } catch(e) {
        try { return ptr.readCString(); } catch(e2) { return null; }
    }
}

var CAPTURED = {
    servers: [],
    files: [],
    prefs: [],
    props: [],
    dns: [],
    traffic_out: 0,
    traffic_in: 0
};

// ===== 1. HOOK connect() - Map all server connections =====
var c_connect = findExport("libc.so", "connect");
if (c_connect) {
    Interceptor.attach(c_connect, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var sockaddr = args[1];
            var len = args[2].toInt32();
            try {
                var family = sockaddr.readU16();
                if (family === 2) { // AF_INET
                    var port = (sockaddr.add(2).readU8() << 8) | sockaddr.add(3).readU8();
                    var ip = sockaddr.add(4).readU8() + "." +
                             sockaddr.add(5).readU8() + "." +
                             sockaddr.add(6).readU8() + "." +
                             sockaddr.add(7).readU8();
                    var entry = ip + ":" + port;
                    if (CAPTURED.servers.indexOf(entry) === -1) {
                        CAPTURED.servers.push(entry);
                        send("CONNECT: " + entry + " (fd=" + fd + ")");
                    }
                }
            } catch(e) {}
        }
    });
    send("[OK] connect() hooked - tracking server connections");
}

// ===== 2. HOOK open/read/write - SharedPreferences & sensitive files =====
var c_open = findExport("libc.so", "open");
var openFds = {}; // fd -> path mapping

if (c_open) {
    Interceptor.attach(c_open, {
        onEnter: function(args) {
            this.path = safeStr(args[0]);
        },
        onLeave: function(retval) {
            var fd = retval.toInt32();
            if (fd >= 0 && this.path) {
                var p = this.path.toLowerCase();
                // Track interesting files
                if (p.indexOf("shared_prefs") !== -1 ||
                    p.indexOf("secure_storage") !== -1 ||
                    p.indexOf("flutter") !== -1 ||
                    p.indexOf("huione") !== -1 ||
                    p.indexOf("keystore") !== -1 ||
                    p.indexOf("token") !== -1 ||
                    p.indexOf("uuid") !== -1 ||
                    p.indexOf("device") !== -1 ||
                    p.indexOf("permission") !== -1 ||
                    p.indexOf("crypto") !== -1) {
                    openFds[fd] = this.path;
                    send("FILE_OPEN: fd=" + fd + " " + this.path);
                    CAPTURED.files.push(this.path);
                }
            }
        }
    });
    send("[OK] open() hooked - tracking file access");
}

// Hook read() to capture SharedPreferences content
var c_read = findExport("libc.so", "read");
if (c_read) {
    Interceptor.attach(c_read, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf = args[1];
            this.isTracked = openFds[this.fd] !== undefined;
        },
        onLeave: function(retval) {
            if (this.isTracked) {
                var bytesRead = retval.toInt32();
                if (bytesRead > 0 && bytesRead < 32768) {
                    var data = safeStr(this.buf, bytesRead);
                    if (data) {
                        // Check for interesting content
                        var dl = data.toLowerCase();
                        if (dl.indexOf("uuid") !== -1 || dl.indexOf("device") !== -1 ||
                            dl.indexOf("permission") !== -1 || dl.indexOf("token") !== -1 ||
                            dl.indexOf("flutter.") !== -1 || dl.indexOf("key") !== -1) {
                            send("FILE_READ[" + openFds[this.fd] + "][" + bytesRead + "B]: " + data.substring(0, 1500));
                            CAPTURED.prefs.push({file: openFds[this.fd], data: data.substring(0, 2000)});
                        }
                    }
                }
            }
        }
    });
    send("[OK] read() hooked - capturing file content");
}

// Hook write() to capture SharedPreferences writes
var c_write = findExport("libc.so", "write");
if (c_write) {
    Interceptor.attach(c_write, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            if (openFds[fd]) {
                var len = args[2].toInt32();
                if (len > 0 && len < 32768) {
                    var data = safeStr(args[1], len);
                    if (data) {
                        send("FILE_WRITE[" + openFds[fd] + "][" + len + "B]: " + data.substring(0, 1500));
                    }
                }
            }
        }
    });
    send("[OK] write() hooked - capturing file writes");
}

// ===== 3. HOOK sendto/recvfrom - Network traffic =====
var c_sendto = findExport("libc.so", "sendto");
if (c_sendto) {
    Interceptor.attach(c_sendto, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            CAPTURED.traffic_out += len;
            // Log first few to see pattern
            if (CAPTURED.traffic_out < 50000 && len > 10 && len < 8192) {
                try {
                    var preview = safeStr(args[1], Math.min(len, 200));
                    if (preview && preview.indexOf("HTTP") !== -1) {
                        send("NET_SEND[" + len + "B]: " + preview.substring(0, 300));
                    }
                } catch(e) {}
            }
        }
    });
    send("[OK] sendto() hooked");
}

var c_recvfrom = findExport("libc.so", "recvfrom");
if (c_recvfrom) {
    Interceptor.attach(c_recvfrom, {
        onEnter: function(args) {
            this.buf = args[1];
            this.maxLen = args[2].toInt32();
        },
        onLeave: function(retval) {
            var bytesRecv = retval.toInt32();
            if (bytesRecv > 0) {
                CAPTURED.traffic_in += bytesRecv;
            }
        }
    });
    send("[OK] recvfrom() hooked");
}

// ===== 4. HOOK __system_property_get - Device fingerprint =====
var prop_get = findExport("libc.so", "__system_property_get");
if (prop_get) {
    Interceptor.attach(prop_get, {
        onEnter: function(args) {
            this.name = safeStr(args[0]);
            this.valBuf = args[1];
        },
        onLeave: function(retval) {
            if (this.name) {
                var n = this.name.toLowerCase();
                if (n.indexOf("product") !== -1 || n.indexOf("brand") !== -1 ||
                    n.indexOf("model") !== -1 || n.indexOf("device") !== -1 ||
                    n.indexOf("serial") !== -1 || n.indexOf("fingerprint") !== -1 ||
                    n.indexOf("android_id") !== -1 || n.indexOf("build") !== -1 ||
                    n.indexOf("hardware") !== -1 || n.indexOf("board") !== -1) {
                    var val = safeStr(this.valBuf);
                    send("DEVICE_PROP: " + this.name + " = " + (val || ""));
                    CAPTURED.props.push({name: this.name, value: val || ""});
                }
            }
        }
    });
    send("[OK] __system_property_get() hooked - tracking device fingerprint");
}

// ===== 5. HOOK getaddrinfo - DNS resolution =====
var c_getaddrinfo = findExport("libc.so", "getaddrinfo");
if (c_getaddrinfo) {
    Interceptor.attach(c_getaddrinfo, {
        onEnter: function(args) {
            var host = safeStr(args[0]);
            if (host) {
                if (CAPTURED.dns.indexOf(host) === -1) {
                    CAPTURED.dns.push(host);
                    send("DNS: " + host);
                }
            }
        }
    });
    send("[OK] getaddrinfo() hooked - tracking DNS queries");
}

// ===== 6. HOOK close() - Clean up fd tracking =====
var c_close = findExport("libc.so", "close");
if (c_close) {
    Interceptor.attach(c_close, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            if (openFds[fd]) {
                delete openFds[fd];
            }
        }
    });
}

// ===== RPC Exports =====
rpc.exports = {
    dump: function() {
        return JSON.stringify(CAPTURED, null, 2);
    },
    servers: function() {
        return CAPTURED.servers;
    },
    props: function() {
        return CAPTURED.props;
    },
    files: function() {
        return CAPTURED.files;
    },
    traffic: function() {
        return {out: CAPTURED.traffic_out, in: CAPTURED.traffic_in};
    }
};

send("=== NATIVE HOOKS v1.0 ACTIVE ===");
send("Monitoring: connect, files, device props, DNS, traffic");
send("Use rpc.exports.dump() to get all captured data");

// Status every 10s
setInterval(function() {
    send("STATUS: servers=" + CAPTURED.servers.length +
         " files=" + CAPTURED.files.length +
         " props=" + CAPTURED.props.length +
         " dns=" + CAPTURED.dns.length +
         " out=" + CAPTURED.traffic_out + "B in=" + CAPTURED.traffic_in + "B");
}, 10000);
