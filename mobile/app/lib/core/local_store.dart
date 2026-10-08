import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Everything the app keeps on the device, other than the session: saved copies of records,
/// pending commands and their attachments (flutter-app-design §5, §6).
///
/// It lives in the platform keystore (Keychain, Android Keystore; WebCrypto-encrypted storage in a
/// browser), so it is encrypted at rest and goes with a wipe. Keys are namespaced: `argus.cache.`,
/// `argus.queue.`, `argus.blob.`.
abstract class LocalStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);

  /// Every entry whose key starts with [prefix].
  Future<Map<String, String>> readPrefix(String prefix);

  /// The keys under [prefix] and when each was written, without reading what they hold: what eviction and
  /// the retention purge need, and, for a store that decrypts on read, much cheaper than [readPrefix].
  Future<Map<String, DateTime>> stamps(String prefix) async => {
        for (final e in (await readPrefix(prefix)).entries)
          e.key: DateTime.tryParse(((jsonDecode(e.value) as Map)['at'] as String?) ?? '') ?? DateTime(0),
      };

  /// Remove an entry by the name [stamps] gave it.
  Future<void> forget(String stamped) => delete(stamped);

  /// Remove every entry under [prefix].
  Future<void> clear(String prefix) async {
    for (final k in (await readPrefix(prefix)).keys) {
      await delete(k);
    }
  }
}

class SecureLocalStore extends LocalStore {
  SecureLocalStore([FlutterSecureStorage? storage]) : _s = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _s;

  @override
  Future<String?> read(String key) => _s.read(key: key);

  @override
  Future<void> write(String key, String value) => _s.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _s.delete(key: key);

  @override
  Future<Map<String, String>> readPrefix(String prefix) async {
    final all = await _s.readAll();
    return {for (final e in all.entries) if (e.key.startsWith(prefix)) e.key: e.value};
  }
}

/// For tests, and for a browser where storage is unavailable.
class MemoryLocalStore extends LocalStore {
  final Map<String, String> data = {};

  @override
  Future<String?> read(String key) async => data[key];

  @override
  Future<void> write(String key, String value) async => data[key] = value;

  @override
  Future<void> delete(String key) async => data.remove(key);

  @override
  Future<Map<String, String>> readPrefix(String prefix) async =>
      {for (final e in data.entries) if (e.key.startsWith(prefix)) e.key: e.value};
}
