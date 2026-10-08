import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:cryptography/cryptography.dart';
import 'package:crypto/crypto.dart' show sha256;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import 'local_store.dart';

/// The saved copies of records, kept as files rather than in the platform keystore.
///
/// The keystore (Keychain, Android Keystore) is made for secrets, not for hundreds of records: every write
/// re-encrypts its whole store, and listing what is kept means decrypting all of it. Here each copy is one
/// file in the app's private storage, encrypted with AES-GCM under a key that lives in the keystore, so the
/// copies are still unreadable without it (flutter-app-design §5.6) — and a sign-out wipes both. When a copy
/// was written is the file's modification time: eviction and the retention purge list the folder without
/// decrypting anything. The copies read most recently are also held in memory, so going back to a screen
/// does not touch the disk.
class FileCacheStore extends LocalStore {
  FileCacheStore({FlutterSecureStorage? keys, Future<Directory> Function()? directory, this.memoryEntries = 80})
      : _keys = keys ?? const FlutterSecureStorage(),
        _directory = directory ?? _defaultDirectory;

  static const _keyName = 'argus.cache-key';

  final FlutterSecureStorage _keys;
  final Future<Directory> Function() _directory;
  final int memoryEntries;
  final _aes = AesGcm.with256bits();
  final _memory = <String, String>{}; // insertion order is recency: the oldest is evicted first

  Directory? _dir;
  SecretKey? _secret;

  static Future<Directory> _defaultDirectory() async =>
      Directory('${(await getApplicationSupportDirectory()).path}/argus-cache');

  Future<Directory> _folder() async {
    final dir = _dir ??= await _directory();
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<SecretKey> _key() async {
    if (_secret != null) return _secret!;
    var stored = await _keys.read(key: _keyName);
    if (stored == null) {
      final r = Random.secure();
      stored = base64Encode(List<int>.generate(32, (_) => r.nextInt(256)));
      await _keys.write(key: _keyName, value: stored);
    }
    return _secret = SecretKey(base64Decode(stored));
  }

  // The key is a name a person could read in a file listing (workspace, path); the file is named by its hash.
  String _fileName(String key) => sha256.convert(utf8.encode(key)).toString();

  Future<File> _file(String key) async => File('${(await _folder()).path}/${_fileName(key)}');

  void _remember(String key, String value) {
    _memory.remove(key);
    _memory[key] = value;
    while (_memory.length > memoryEntries) {
      _memory.remove(_memory.keys.first);
    }
  }

  @override
  Future<String?> read(String key) async {
    final hit = _memory.remove(key);
    if (hit != null) {
      _memory[key] = hit;
      return hit;
    }
    final f = await _file(key);
    if (!await f.exists()) return null;
    try {
      final box = SecretBox.fromConcatenation(await f.readAsBytes(),
          nonceLength: _aes.nonceLength, macLength: _aes.macAlgorithm.macLength);
      final value = utf8.decode(await _aes.decrypt(box, secretKey: await _key()));
      final stored = jsonDecode(value) as Map<String, dynamic>;
      if (stored['key'] != key) return null; // a hash collision, however unlikely, is not this copy
      _remember(key, stored['value'] as String);
      return stored['value'] as String;
    } catch (_) {
      await f.delete(); // unreadable (a key from before a reinstall): gone, as if never kept
      return null;
    }
  }

  @override
  Future<void> write(String key, String value) async {
    _remember(key, value);
    final box = await _aes.encrypt(utf8.encode(jsonEncode({'key': key, 'value': value})), secretKey: await _key());
    final f = await _file(key);
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsBytes(box.concatenation(), flush: true);
    await tmp.rename(f.path);
  }

  @override
  Future<void> delete(String key) async {
    _memory.remove(key);
    final f = await _file(key);
    if (await f.exists()) await f.delete();
  }

  /// Which key a file holds is only known by decrypting it, so this is the slow way: [stamps] is not.
  @override
  Future<Map<String, String>> readPrefix(String prefix) async {
    final out = <String, String>{};
    for (final f in (await _folder()).listSync().whereType<File>()) {
      if (f.path.endsWith('.tmp')) continue;
      try {
        final box = SecretBox.fromConcatenation(await f.readAsBytes(),
            nonceLength: _aes.nonceLength, macLength: _aes.macAlgorithm.macLength);
        final stored = jsonDecode(utf8.decode(await _aes.decrypt(box, secretKey: await _key()))) as Map;
        final key = stored['key'] as String;
        if (key.startsWith(prefix)) out[key] = stored['value'] as String;
      } catch (_) {
        await f.delete();
      }
    }
    return out;
  }

  /// Keyed by file name rather than by key: [forget] removes what this lists.
  @override
  Future<Map<String, DateTime>> stamps(String prefix) async => {
        for (final f in (await _folder()).listSync().whereType<File>())
          if (!f.path.endsWith('.tmp')) f.uri.pathSegments.last: f.lastModifiedSync(),
      };

  @override
  Future<void> forget(String stamped) async {
    _memory.clear(); // which key that file held is not known without reading it: forget them all, cheaply
    final f = File('${(await _folder()).path}/$stamped');
    if (await f.exists()) await f.delete();
  }

  @override
  Future<void> clear(String prefix) async {
    _memory.clear();
    final dir = await _folder();
    if (await dir.exists()) await dir.delete(recursive: true);
  }
}
