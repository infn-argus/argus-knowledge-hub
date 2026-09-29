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
}

class SecureLocalStore implements LocalStore {
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
class MemoryLocalStore implements LocalStore {
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
