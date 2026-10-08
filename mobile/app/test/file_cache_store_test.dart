import 'dart:io';

import 'package:argus_field/core/file_cache_store.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory dir;
  FileCacheStore store() => FileCacheStore(directory: () async => dir, memoryEntries: 2);

  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    dir = await Directory.systemTemp.createTemp('argus-cache-test');
  });
  tearDown(() async {
    if (await dir.exists()) await dir.delete(recursive: true);
  });

  test('a copy is written encrypted and read back, by another instance too', () async {
    await store().write('argus.cache.x', '{"secret":"ion pump GUNSIP01"}');
    final files = dir.listSync().whereType<File>().toList();
    expect(files, hasLength(1));
    expect(String.fromCharCodes(files.single.readAsBytesSync()), isNot(contains('GUNSIP01')),
        reason: 'nothing readable on disk');
    expect(files.single.uri.pathSegments.last, isNot(contains('argus')), reason: 'nor in the file name');
    expect(await store().read('argus.cache.x'), '{"secret":"ion pump GUNSIP01"}');
  });

  test('when each copy was written is listed without decrypting, and forgotten by that name', () async {
    final s = store();
    await s.write('argus.cache.a', '1');
    await s.write('argus.cache.b', '2');
    final stamps = await s.stamps('argus.cache.');
    expect(stamps, hasLength(2));
    await s.forget(stamps.keys.first);
    expect((await s.stamps('argus.cache.')), hasLength(1));
  });

  test('a copy written under another key (a reinstall) is dropped, not misread', () async {
    await store().write('argus.cache.x', 'old');
    FlutterSecureStorage.setMockInitialValues({}); // the keystore lost its key
    expect(await store().read('argus.cache.x'), isNull);
    expect(dir.listSync(), isEmpty);
  });

  test('clearing removes every copy', () async {
    final s = store();
    await s.write('argus.cache.a', '1');
    await s.clear('argus.cache.');
    expect(await s.read('argus.cache.a'), isNull);
  });
}
