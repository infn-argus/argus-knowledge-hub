import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

/// The files a pending command carries — a photo, a video, a recorded note, a place — until the server has
/// them (flutter-app-design §5.5). Each is a file of its own in the app's private storage, encrypted with
/// AES-GCM under a key kept in the keystore: the keystore holds secrets, not a 200 MB video.
abstract class BlobStore {
  Future<void> put(String id, Uint8List bytes);
  Future<Uint8List?> get(String id);
  Future<void> delete(String id);
  Future<void> clear();
}

class MemoryBlobStore implements BlobStore {
  final Map<String, Uint8List> data = {};

  @override
  Future<void> put(String id, Uint8List bytes) async => data[id] = bytes;

  @override
  Future<Uint8List?> get(String id) async => data[id];

  @override
  Future<void> delete(String id) async => data.remove(id);

  @override
  Future<void> clear() async => data.clear();
}

class FileBlobStore implements BlobStore {
  FileBlobStore({FlutterSecureStorage? keys, Future<Directory> Function()? directory})
      : _keys = keys ?? const FlutterSecureStorage(),
        _directory = directory ?? _defaultDirectory;

  static const _keyName = 'argus.blob-key';

  final FlutterSecureStorage _keys;
  final Future<Directory> Function() _directory;
  final _aes = AesGcm.with256bits();
  SecretKey? _secret;

  static Future<Directory> _defaultDirectory() async =>
      Directory('${(await getApplicationSupportDirectory()).path}/argus-blobs');

  Future<Directory> _folder() async {
    final dir = await _directory();
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

  // A local id is a UUID the app made: safe as a file name.
  Future<File> _file(String id) async => File('${(await _folder()).path}/${id.replaceAll(RegExp(r'[^A-Za-z0-9-]'), '_')}');

  @override
  Future<void> put(String id, Uint8List bytes) async {
    final box = await _aes.encrypt(bytes, secretKey: await _key());
    final f = await _file(id);
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsBytes(box.concatenation(), flush: true);
    await tmp.rename(f.path);
  }

  @override
  Future<Uint8List?> get(String id) async {
    final f = await _file(id);
    if (!await f.exists()) return null;
    try {
      final box = SecretBox.fromConcatenation(await f.readAsBytes(),
          nonceLength: _aes.nonceLength, macLength: _aes.macAlgorithm.macLength);
      return Uint8List.fromList(await _aes.decrypt(box, secretKey: await _key()));
    } catch (_) {
      return null; // a key from before a reinstall: the file cannot be read, and is not sent half-read
    }
  }

  @override
  Future<void> delete(String id) async {
    final f = await _file(id);
    if (await f.exists()) await f.delete();
  }

  @override
  Future<void> clear() async {
    final dir = await _directory();
    if (await dir.exists()) await dir.delete(recursive: true);
  }
}
