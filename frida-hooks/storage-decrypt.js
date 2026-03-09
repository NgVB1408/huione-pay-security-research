/**
 * Frida Script - FULL Huione Pay Crypto Interceptor v2.0
 *
 * Usage: frida -U -f com.huione.pay -l frida_decrypt_storage.js --no-pause
 *
 * ENCRYPTION LAYERS:
 * ==================
 * Layer 1 - FlutterSecureStorage (Java):
 *    - AES-128-CBC-PKCS7Padding (IV 16 bytes prepended)
 *    - AES key wrapped by RSA (Android Keystore)
 *    - Key prefix: "VGhpcyBpcyB0aGUgcHJlZml4IGZvciBhIHNlY3VyZSBzdG9yYWdlCg"
 *
 * Layer 2 - EncryptedSharedPreferences (Google Tink):
 *    - Keys: AES-256-SIV (deterministic AEAD)
 *    - Values: AES-256-GCM
 *    - Master key: Android Keystore "_androidx_security_master_key_"
 *
 * Layer 3 - NDK Native Crypto (libcryption.so):
 *    - ECDH P-256 key exchange (shared secret)
 *    - AES-128-ECB channel encrypt/decrypt (using ECDH secret)
 *    - AES-128-ECB private key encrypt/decrypt (using generateAesKey(id,time,info))
 *    - ECDSA-P256-SHA1 signing/verification
 *
 * Layer 4 - SDK Data Encryption (Java):
 *    - AES-256-ECB with hardcoded key "keyhead_project_xhui_one_keytail"
 *    - URL encode -> Base64 -> AES
 *
 * Flutter MethodChannel "crypto" methods:
 *    genKeyPair, exchange, encryptChannel, decryptChannel,
 *    encryptPrivate, decryptPrivate, sign, verifySign, decryptSDK, test
 */

'use strict';

// ===== COLOR HELPERS =====
var Color = {
    RED: '\x1b[31m',
    GREEN: '\x1b[32m',
    YELLOW: '\x1b[33m',
    BLUE: '\x1b[34m',
    MAGENTA: '\x1b[35m',
    CYAN: '\x1b[36m',
    RESET: '\x1b[0m'
};

function log(tag, msg) {
    console.log(Color.GREEN + '[+] ' + Color.CYAN + tag + Color.RESET + ': ' + msg);
}
function logData(tag, key, value) {
    console.log(Color.YELLOW + '[DATA] ' + Color.CYAN + tag + Color.RESET + ' | ' + Color.GREEN + key + Color.RESET + ' = ' + value);
}
function logCrypto(tag, msg) {
    console.log(Color.MAGENTA + '[CRYPTO] ' + Color.CYAN + tag + Color.RESET + ': ' + msg);
}
function logWarn(msg) {
    console.log(Color.RED + '[!] ' + Color.RESET + msg);
}

// ===== COLLECTED DATA =====
var collectedData = {};
var collectedKeys = {};
var collectedECDH = {};

// ====================================================================
// HOOK 1: FlutterSecureStorage - Intercept ALL read/write operations
// ====================================================================
function hookFlutterSecureStoragePlugin() {
    try {
        var pluginClass = Java.use('p019H.C0046f');
        log('Hook', 'FlutterSecureStorage plugin class found');
    } catch (e) {
        logWarn('FlutterSecureStorage plugin class not found (p019H.C0046f)');
    }

    // Hook the storage manager class C0041a (H.a)
    try {
        var storageManager = Java.use('p019H.C0041a');

        // Hook decrypt (m158b) - called when reading values
        storageManager.m158b.implementation = function (encryptedStr) {
            var decrypted = this.m158b(encryptedStr);
            logData('FSS_DECRYPT', 'encrypted=' + (encryptedStr ? encryptedStr.substring(0, 40) + '...' : 'null'), decrypted);
            return decrypted;
        };
        log('Hook', 'C0041a.m158b (decrypt) hooked');

        // Hook write (m164h) - called when storing values
        storageManager.m164h.implementation = function (key, value) {
            logData('FSS_WRITE', key, value);
            collectedData['fss_' + key] = value;
            this.m164h(key, value);
        };
        log('Hook', 'C0041a.m164h (write) hooked');

        // Hook readAll (m163g) - dump all values
        storageManager.m163g.implementation = function () {
            var result = this.m163g();
            log('FSS_READ_ALL', 'Dumping all FlutterSecureStorage entries:');
            var iter = result.entrySet().iterator();
            while (iter.hasNext()) {
                var entry = iter.next();
                var k = entry.getKey().toString();
                var v = entry.getValue().toString();
                logData('FSS_STORED', k, v);
                collectedData['fss_' + k] = v;
            }
            return result;
        };
        log('Hook', 'C0041a.m163g (readAll) hooked');

    } catch (e) {
        logWarn('C0041a hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 2: RSA Key Unwrap - Capture raw AES key
// ====================================================================
function hookRSAKeyUnwrap() {
    try {
        var rsaCipher = Java.use('p002B.C0006a');

        rsaCipher.m25r.implementation = function (wrappedKey) {
            var unwrappedKey = this.m25r(wrappedKey);
            logCrypto('RSA_UNWRAP', 'AES key unwrapped from Android Keystore');

            var SecretKeySpec = Java.use('javax.crypto.spec.SecretKeySpec');
            try {
                var keyBytes = unwrappedKey.getEncoded();
                if (keyBytes) {
                    var hexKey = bytesToHex(keyBytes);
                    logCrypto('AES_KEY', 'FlutterSecureStorage AES key: ' + hexKey);
                    collectedKeys['fss_aes_key'] = hexKey;
                }
            } catch (ex) {
                logWarn('Could not extract key bytes: ' + ex);
            }
            return unwrappedKey;
        };
        log('Hook', 'RSA key unwrap (p002B.C0006a.m25r) hooked');

    } catch (e) {
        logWarn('RSA unwrap hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 3: AES Cipher.doFinal - Intercept all AES operations
// ====================================================================
function hookAESCipher() {
    try {
        var Cipher = Java.use('javax.crypto.Cipher');

        Cipher.doFinal.overload('[B').implementation = function (input) {
            var result = this.doFinal(input);
            var algo = this.getAlgorithm();

            if (algo && algo.indexOf('AES') !== -1) {
                try {
                    var inputStr = bytesToString(input);
                    var resultStr = bytesToString(result);

                    if (input.length < 2000) {
                        logData('AES_' + algo, 'input(' + input.length + ')', inputStr.substring(0, 200));
                    }
                    if (result.length < 2000) {
                        logData('AES_' + algo, 'output(' + result.length + ')', resultStr.substring(0, 200));
                    }
                } catch (ex) {}
            }
            return result;
        };
        log('Hook', 'Cipher.doFinal([B) hooked');
    } catch (e) {
        logWarn('Cipher hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 4: SharedPreferences - Intercept reads for sensitive keys
// ====================================================================
function hookSharedPreferences() {
    try {
        var SP = Java.use('android.app.SharedPreferencesImpl');

        SP.getString.implementation = function (key, defValue) {
            var result = this.getString(key, defValue);

            if (key && (key.indexOf('APP_') === 0 ||
                        key.indexOf('Flutter') !== -1 ||
                        key.indexOf('VGhp') !== -1 ||
                        key.indexOf('token') !== -1 ||
                        key.indexOf('user') !== -1 ||
                        key.indexOf('key') !== -1 ||
                        key.indexOf('__androidx_security') !== -1)) {
                logData('SP_READ', key, result ? result.substring(0, 200) : 'null');
                collectedData['sp_' + key] = result;
            }
            return result;
        };
        log('Hook', 'SharedPreferences.getString hooked');

    } catch (e) {
        logWarn('SharedPreferences hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 5: OkHttp Network - Intercept API requests with tokens
// ====================================================================
function hookNetworkRequests() {
    try {
        var Buffer = Java.use('okio.Buffer');
        var RealCall = Java.use('okhttp3.internal.connection.RealCall');

        RealCall.getResponseWithInterceptorChain.implementation = function () {
            var request = this.getOriginalRequest();
            var url = request.url().toString();
            var method = request.method();

            if (url.indexOf('foundation') !== -1 ||
                url.indexOf('login') !== -1 ||
                url.indexOf('token') !== -1 ||
                url.indexOf('transfer') !== -1 ||
                url.indexOf('payment') !== -1 ||
                url.indexOf('wallet') !== -1 ||
                url.indexOf('user') !== -1 ||
                url.indexOf('account') !== -1 ||
                url.indexOf('crypto') !== -1) {

                log('HTTP', method + ' ' + url);

                var headers = request.headers();
                for (var i = 0; i < headers.size(); i++) {
                    var name = headers.name(i);
                    if (name.toLowerCase().indexOf('auth') !== -1 ||
                        name.toLowerCase().indexOf('token') !== -1 ||
                        name.toLowerCase().indexOf('cookie') !== -1 ||
                        name.toLowerCase().indexOf('x-') === 0) {
                        logData('HEADER', name, headers.value(i));
                    }
                }

                var body = request.body();
                if (body) {
                    try {
                        var buffer = Buffer.$new();
                        body.writeTo(buffer);
                        var bodyStr = buffer.readUtf8();
                        if (bodyStr.length < 5000) {
                            logData('REQ_BODY', method + ' ' + url.split('?')[0], bodyStr);
                        }
                    } catch (ex) {}
                }
            }

            return this.getResponseWithInterceptorChain();
        };
        log('Hook', 'OkHttp RealCall hooked');

    } catch (e) {
        logWarn('Network hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 6: NDK Crypto - Hook ALL AndroidNDKEncryption native methods
//         via the Flutter MethodChannel handler (C1534c / Cryption)
// ====================================================================
function hookNDKCryptoMethodChannel() {
    try {
        var cryptoPlugin = Java.use('com.financial.crypto.C1534c');

        cryptoPlugin.onMethodCall.implementation = function (methodCall, result) {
            var method = methodCall.method;
            log('CRYPTO_CHANNEL', 'Method called: ' + method);

            // Log all arguments
            try {
                var args = methodCall.arguments();
                if (args) {
                    logData('CRYPTO_ARGS', method, args.toString().substring(0, 500));
                }
            } catch (ex) {}

            // Wrap result to intercept the response
            var WrappedResult = Java.registerClass({
                name: 'com.frida.WrappedResult_' + Date.now(),
                implements: [Java.use('io.flutter.plugin.common.MethodChannel$Result')],
                fields: { origResult: 'Lio/flutter/plugin/common/MethodChannel$Result;' },
                methods: {
                    success: function (obj) {
                        if (obj !== null) {
                            logData('CRYPTO_RESULT', method, obj.toString().substring(0, 1000));
                            collectedData['crypto_' + method + '_' + Date.now()] = obj.toString();
                        }
                        this.origResult.value.success(obj);
                    },
                    error: function (code, msg, details) {
                        logWarn('CRYPTO_ERROR [' + method + ']: ' + code + ' - ' + msg);
                        this.origResult.value.error(code, msg, details);
                    },
                    notImplemented: function () {
                        this.origResult.value.notImplemented();
                    }
                }
            });

            var wrapped = WrappedResult.$new();
            wrapped.origResult.value = result;
            this.onMethodCall(methodCall, wrapped);
        };
        log('Hook', 'NDK Crypto MethodChannel (C1534c) hooked - ALL methods intercepted');

    } catch (e) {
        logWarn('NDK Crypto MethodChannel hook failed: ' + e + ', trying direct hooks...');
        hookNDKCryptoDirect();
    }
}

// Direct hooks on AndroidNDKEncryption JNI methods (fallback)
function hookNDKCryptoDirect() {
    try {
        var ndk = Java.use('com.financial.crypto.AndroidNDKEncryption');

        // getKeyPairStr - generates ECC P-256 keypair
        ndk.getKeyPairStr.implementation = function () {
            var result = this.getKeyPairStr();
            logCrypto('GEN_KEYPAIR', 'Generated ECC P-256 keypair');
            var parts = result.split('concat');
            if (parts.length === 2) {
                logCrypto('PRIVATE_KEY', parts[0].substring(0, 80) + '...');
                logCrypto('PUBLIC_KEY', parts[1].substring(0, 80) + '...');
                collectedKeys['ecc_private'] = parts[0];
                collectedKeys['ecc_public'] = parts[1];
            }
            return result;
        };

        // exchangeECDHPublic - ECDH key agreement
        ndk.exchangeECDHPublic.implementation = function (privateKey, publicKey) {
            var sharedSecret = this.exchangeECDHPublic(privateKey, publicKey);
            logCrypto('ECDH_EXCHANGE', 'Shared secret computed');
            logCrypto('ECDH_SECRET', sharedSecret.substring(0, 100) + '...');
            collectedKeys['ecdh_secret_' + Date.now()] = sharedSecret;
            collectedECDH['last_private'] = privateKey;
            collectedECDH['last_peer_public'] = publicKey;
            collectedECDH['last_secret'] = sharedSecret;
            return sharedSecret;
        };

        // encryptChannel - AES-128-ECB with ECDH key
        ndk.encryptChannel.implementation = function (key, message) {
            var encrypted = this.encryptChannel(key, message);
            logCrypto('ENCRYPT_CHANNEL', 'Key=' + key.substring(0, 40) + '...');
            logData('ENCRYPT_CHANNEL', 'plaintext', message.substring(0, 500));
            logData('ENCRYPT_CHANNEL', 'ciphertext', encrypted.substring(0, 200));
            return encrypted;
        };

        // decryptChannel - AES-128-ECB with ECDH key
        ndk.decryptChannel.implementation = function (key, ciphertext) {
            var decrypted = this.decryptChannel(key, ciphertext);
            logCrypto('DECRYPT_CHANNEL', 'Key=' + key.substring(0, 40) + '...');
            logData('DECRYPT_CHANNEL', 'ciphertext', ciphertext.substring(0, 200));
            logData('DECRYPT_CHANNEL', 'plaintext', decrypted.substring(0, 500));
            collectedData['channel_' + Date.now()] = decrypted;
            return decrypted;
        };

        // encryptPrivateKey - AES key derived from (id, time, info)
        ndk.encryptPrivateKey.implementation = function (privateKey, id, time, info) {
            var encrypted = this.encryptPrivateKey(privateKey, id, time, info);
            logCrypto('ENCRYPT_PRIVKEY', 'id=' + id + ', time=' + time + ', info=' + info);
            logData('ENCRYPT_PRIVKEY', 'privateKey', privateKey.substring(0, 80) + '...');
            logData('ENCRYPT_PRIVKEY', 'encrypted', encrypted.substring(0, 200));
            return encrypted;
        };

        // decryptPrivateKey - AES key derived from (id, time, info)
        ndk.decryptPrivateKey.implementation = function (encoded, id, time, info) {
            var decrypted = this.decryptPrivateKey(encoded, id, time, info);
            logCrypto('DECRYPT_PRIVKEY', 'id=' + id + ', time=' + time + ', info=' + info);
            logData('DECRYPT_PRIVKEY', 'encoded', encoded.substring(0, 200));
            logData('DECRYPT_PRIVKEY', 'privateKey', decrypted.substring(0, 200));
            collectedKeys['decrypted_privkey_' + Date.now()] = decrypted;
            return decrypted;
        };

        // sign - ECDSA-P256-SHA1
        ndk.sign.implementation = function (privateKey, message) {
            var signature = this.sign(privateKey, message);
            logCrypto('SIGN', 'ECDSA-P256-SHA1');
            logData('SIGN', 'message', message.substring(0, 200));
            logData('SIGN', 'signature', signature.substring(0, 200));
            return signature;
        };

        // verifySign
        ndk.verifySign.implementation = function (publicKey, message, signed) {
            var valid = this.verifySign(publicKey, message, signed);
            logCrypto('VERIFY', 'valid=' + valid);
            logData('VERIFY', 'message', message.substring(0, 200));
            return valid;
        };

        log('Hook', 'AndroidNDKEncryption - ALL 7 native methods hooked directly');

    } catch (e) {
        logWarn('Direct NDK hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 7: SDK Decryption (AbstractC0229a.m531q) - Hardcoded AES-256-ECB
//         Key: "keyhead_project_xhui_one_keytail"
// ====================================================================
function hookSDKDecrypt() {
    try {
        var sdkClass = Java.use('p058a.AbstractC0229a');

        sdkClass.m531q.implementation = function (encryptedData) {
            var decrypted = this.m531q(encryptedData);
            logCrypto('DECRYPT_SDK', 'AES-256-ECB (hardcoded key)');
            logData('DECRYPT_SDK', 'input', encryptedData ? encryptedData.substring(0, 200) : 'null');
            logData('DECRYPT_SDK', 'output', decrypted ? decrypted.substring(0, 500) : 'null');
            collectedData['sdk_' + Date.now()] = decrypted;
            return decrypted;
        };
        log('Hook', 'SDK decrypt (AbstractC0229a.m531q) hooked');

    } catch (e) {
        logWarn('SDK decrypt hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 8: EncryptedSharedPreferences - Intercept getAll/getString
// ====================================================================
function hookEncryptedSharedPreferences() {
    try {
        var ESP = Java.use('androidx.security.crypto.EncryptedSharedPreferences');

        ESP.getAll.implementation = function () {
            var all = this.getAll();
            log('ESP_GETALL', 'Decrypted EncryptedSharedPreferences entries:');
            var iter = all.entrySet().iterator();
            while (iter.hasNext()) {
                var entry = iter.next();
                var k = entry.getKey() ? entry.getKey().toString() : 'null';
                var v = entry.getValue() ? entry.getValue().toString() : 'null';
                logData('ESP', k, v.substring(0, 500));
                collectedData['esp_' + k] = v;
            }
            return all;
        };

        ESP.getString.implementation = function (key, defValue) {
            var result = this.getString(key, defValue);
            if (result) {
                logData('ESP_GET', key, result.substring(0, 500));
                collectedData['esp_' + key] = result;
            }
            return result;
        };

        ESP.getInt.implementation = function (key, defValue) {
            var result = this.getInt(key, defValue);
            logData('ESP_GET_INT', key, '' + result);
            return result;
        };

        ESP.getLong.implementation = function (key, defValue) {
            var result = this.getLong(key, defValue);
            logData('ESP_GET_LONG', key, '' + result);
            return result;
        };

        ESP.getBoolean.implementation = function (key, defValue) {
            var result = this.getBoolean(key, defValue);
            logData('ESP_GET_BOOL', key, '' + result);
            return result;
        };

        log('Hook', 'EncryptedSharedPreferences (all getters) hooked');

    } catch (e) {
        logWarn('EncryptedSharedPreferences hook failed: ' + e);
    }
}

// ====================================================================
// HOOK 9: SQLite Database - Intercept queries
// ====================================================================
function hookSQLite() {
    try {
        var SQLiteDB = Java.use('android.database.sqlite.SQLiteDatabase');

        SQLiteDB.rawQuery.overload('java.lang.String', '[Ljava.lang.String;').implementation = function (sql, args) {
            var result = this.rawQuery(sql, args);
            if (sql.toLowerCase().indexOf('message') !== -1 ||
                sql.toLowerCase().indexOf('search') !== -1 ||
                sql.toLowerCase().indexOf('user') !== -1 ||
                sql.toLowerCase().indexOf('token') !== -1 ||
                sql.toLowerCase().indexOf('key') !== -1) {
                logData('SQL_QUERY', 'query', sql);
                if (args) {
                    logData('SQL_QUERY', 'args', Java.use('java.util.Arrays').toString(args));
                }
            }
            return result;
        };

        SQLiteDB.execSQL.overload('java.lang.String').implementation = function (sql) {
            if (sql.toLowerCase().indexOf('insert') !== -1 ||
                sql.toLowerCase().indexOf('create') !== -1 ||
                sql.toLowerCase().indexOf('update') !== -1) {
                logData('SQL_EXEC', 'statement', sql.substring(0, 500));
            }
            this.execSQL(sql);
        };

        log('Hook', 'SQLiteDatabase (rawQuery + execSQL) hooked');

    } catch (e) {
        logWarn('SQLite hook failed: ' + e);
    }
}

// ====================================================================
// DUMP: Full SharedPreferences + Database dump on demand
// ====================================================================
function dumpAllSharedPrefs() {
    Java.perform(function () {
        try {
            var ActivityThread = Java.use('android.app.ActivityThread');
            var context = ActivityThread.currentApplication().getApplicationContext();
            var dataDir = context.getApplicationInfo().dataDir.value;

            log('DUMP', 'App data dir: ' + dataDir);

            var File = Java.use('java.io.File');
            var spDir = File.$new(dataDir + '/shared_prefs');

            if (spDir.exists()) {
                var files = spDir.listFiles();
                log('DUMP', '=== SharedPreferences files (' + files.length + ') ===');
                for (var i = 0; i < files.length; i++) {
                    log('SP_FILE', files[i].getName() + ' (' + files[i].length() + ' bytes)');
                }
            }

            // Dump FlutterSecureStorage (encrypted values)
            var sp = context.getSharedPreferences('FlutterSecureStorage', 0);
            var all = sp.getAll();
            var iter = all.entrySet().iterator();
            log('DUMP', '=== FlutterSecureStorage (' + all.size() + ' entries) ===');
            while (iter.hasNext()) {
                var entry = iter.next();
                logData('FSS_RAW', entry.getKey().toString(),
                    entry.getValue().toString().substring(0, 100) + '...');
            }

            // Dump FlutterSecureKeyStorage (wrapped AES key)
            var spKey = context.getSharedPreferences('FlutterSecureKeyStorage', 0);
            var allKeys = spKey.getAll();
            var iterK = allKeys.entrySet().iterator();
            log('DUMP', '=== FlutterSecureKeyStorage (RSA-wrapped AES keys) ===');
            while (iterK.hasNext()) {
                var entryK = iterK.next();
                logData('KEY_WRAPPED', entryK.getKey().toString(), entryK.getValue().toString());
            }

            // Try to dump databases
            var dbDir = File.$new(dataDir + '/databases');
            if (dbDir.exists()) {
                var dbFiles = dbDir.listFiles();
                log('DUMP', '=== Database files (' + dbFiles.length + ') ===');
                for (var j = 0; j < dbFiles.length; j++) {
                    log('DB_FILE', dbFiles[j].getName() + ' (' + dbFiles[j].length() + ' bytes)');
                }
            }

            // Dump app cache dir
            var cacheDir = File.$new(dataDir + '/cache');
            if (cacheDir.exists()) {
                var cacheFiles = cacheDir.listFiles();
                log('DUMP', '=== Cache files (' + (cacheFiles ? cacheFiles.length : 0) + ') ===');
            }

        } catch (e) {
            logWarn('Dump failed: ' + e);
        }
    });
}

// Force trigger EncryptedSharedPreferences decryption
function forceDecryptESP() {
    Java.perform(function () {
        try {
            var ActivityThread = Java.use('android.app.ActivityThread');
            var context = ActivityThread.currentApplication().getApplicationContext();
            var MasterKey = Java.use('androidx.security.crypto.MasterKey$Builder');
            var ESP = Java.use('androidx.security.crypto.EncryptedSharedPreferences');
            var PrefKeyScheme = Java.use('androidx.security.crypto.EncryptedSharedPreferences$PrefKeyEncryptionScheme');
            var PrefValueScheme = Java.use('androidx.security.crypto.EncryptedSharedPreferences$PrefValueEncryptionScheme');

            var masterKey = MasterKey.$new(context).setKeyScheme(
                Java.use('androidx.security.crypto.MasterKey$KeyScheme').AES256_GCM.value
            ).build();

            // Try common EncryptedSharedPreferences file names
            var names = ['FlutterSecureStorage', 'encrypted_prefs', 'secure_prefs', 'flutter_secure_storage'];
            for (var i = 0; i < names.length; i++) {
                try {
                    var sp = ESP.create(context, names[i], masterKey,
                        PrefKeyScheme.AES256_SIV.value,
                        PrefValueScheme.AES256_GCM.value);
                    var all = sp.getAll();
                    if (all.size() > 0) {
                        log('FORCE_ESP', 'Decrypted ' + names[i] + ' (' + all.size() + ' entries):');
                        var iter = all.entrySet().iterator();
                        while (iter.hasNext()) {
                            var entry = iter.next();
                            logData('ESP_DECRYPTED', entry.getKey().toString(),
                                entry.getValue() ? entry.getValue().toString() : 'null');
                        }
                    }
                } catch (ex) {}
            }
        } catch (e) {
            logWarn('Force ESP decrypt failed: ' + e);
        }
    });
}

// ====================================================================
// UTILITY FUNCTIONS
// ====================================================================
function bytesToHex(bytes) {
    var hex = '';
    for (var i = 0; i < bytes.length; i++) {
        hex += ('0' + (bytes[i] & 0xFF).toString(16)).slice(-2);
    }
    return hex;
}

function bytesToString(bytes) {
    try {
        var str = '';
        for (var i = 0; i < bytes.length && i < 500; i++) {
            var b = bytes[i] & 0xFF;
            if (b >= 32 && b < 127) {
                str += String.fromCharCode(b);
            } else {
                str += '.';
            }
        }
        return str;
    } catch (e) {
        return '[binary data]';
    }
}

// ====================================================================
// RPC EXPORTS - Call from Python/CLI
// ====================================================================
rpc.exports = {
    dump: function () {
        Java.perform(function () {
            dumpAllSharedPrefs();
        });
    },
    forceDecrypt: function () {
        forceDecryptESP();
    },
    getCollected: function () {
        return JSON.stringify(collectedData, null, 2);
    },
    getKeys: function () {
        return JSON.stringify(collectedKeys, null, 2);
    },
    getECDH: function () {
        return JSON.stringify(collectedECDH, null, 2);
    }
};

// ====================================================================
// MAIN - Start all hooks
// ====================================================================
console.log(Color.RED + '\n========================================================');
console.log('  HUIONE PAY - Full Crypto Interceptor v2.0');
console.log('  9 Hook Points | 4 Encryption Layers | NDK + Java + Tink');
console.log('========================================================' + Color.RESET + '\n');

Java.perform(function () {
    log('Init', 'Starting hooks...\n');

    // Layer 1: FlutterSecureStorage
    hookFlutterSecureStoragePlugin();
    hookRSAKeyUnwrap();

    // Layer 2: EncryptedSharedPreferences (Tink)
    hookEncryptedSharedPreferences();

    // Layer 3: NDK Native Crypto (libcryption.so)
    hookNDKCryptoMethodChannel();
    hookNDKCryptoDirect();

    // Layer 4: SDK hardcoded AES
    hookSDKDecrypt();

    // Generic hooks
    hookAESCipher();
    hookSharedPreferences();
    hookNetworkRequests();
    hookSQLite();

    console.log('');
    log('Init', 'ALL 9 HOOK POINTS INSTALLED!');
    log('Init', '');
    log('Usage', 'rpc.exports.dump()         - Dump all SharedPreferences & DB files');
    log('Usage', 'rpc.exports.forceDecrypt()  - Force decrypt EncryptedSharedPreferences');
    log('Usage', 'rpc.exports.getCollected()  - Get all intercepted data as JSON');
    log('Usage', 'rpc.exports.getKeys()       - Get all captured crypto keys');
    log('Usage', 'rpc.exports.getECDH()       - Get ECDH key exchange data');
    log('Init', '\nWaiting for app activity...\n');
});
