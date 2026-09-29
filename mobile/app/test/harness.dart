import 'dart:typed_data';

import 'package:argus_field/app/app.dart';
import 'package:argus_field/app/providers.dart';
import 'package:argus_field/app/router.dart';
import 'package:argus_field/core/config.dart';
import 'package:argus_field/domain/capture.dart';
import 'package:argus_field/features/capture/photo_source.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';

const testConfig = AppConfig(
  environment: 'development',
  apiBase: 'https://argus.test',
  linkHost: 'argus.test',
  oidcIssuer: '',
  oidcClientId: '',
  oidcRedirect: '',
  appVersion: '0.2.0',
);

const signedIn = {
  'argus.session': '{"accessToken":"tok","authType":"token","workspaceId":"$workspaceId",'
      '"workspaceName":"Slice","deviceId":"dev-1"}',
};

/// A camera that always returns the same small JPEG header, 3000 bytes long.
class FakePhotos implements PhotoSource {
  int taken = 0;

  @override
  Future<PickedPhoto?> take() async {
    taken++;
    final bytes = Uint8List(3000)..setAll(0, [0xFF, 0xD8, 0xFF, 0xE0]);
    return PickedPhoto(bytes: bytes, name: 'IMG_$taken.jpg', mimeType: 'image/jpeg');
  }
}

class Running {
  Running(this.server, this.photos, this.tester);

  final FakeArgus server;
  final FakePhotos photos;
  final WidgetTester tester;

  Future<void> go(String path) async {
    ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider).go(path);
    await tester.pumpAndSettle();
  }

  Future<void> tap(String key) async {
    final f = find.byKey(Key(key));
    await tester.ensureVisible(f);
    await tester.pumpAndSettle();
    await tester.tap(f);
    await tester.pumpAndSettle();
  }

  Future<void> type(String key, String text) async {
    final f = find.byKey(Key(key));
    await tester.ensureVisible(f);
    await tester.enterText(f, text);
    await tester.pump();
  }
}

Future<Running> start(WidgetTester tester, {Map<String, String> stored = signedIn}) async {
  FlutterSecureStorage.setMockInitialValues(Map.of(stored));
  await tester.binding.setSurfaceSize(const Size(420, 1400));
  final server = FakeArgus();
  final photos = FakePhotos();
  await tester.pumpWidget(ProviderScope(
    retry: retryPolicy,
    overrides: [
      configProvider.overrideWithValue(testConfig),
      httpClientProvider.overrideWithValue(server.client),
      photoSourceProvider.overrideWithValue(photos),
    ],
    child: const ArgusFieldApp(),
  ));
  await tester.pumpAndSettle();
  return Running(server, photos, tester);
}

