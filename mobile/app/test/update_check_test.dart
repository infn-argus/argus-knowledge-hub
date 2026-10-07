import 'dart:convert';

import 'package:argus_field/core/config.dart';
import 'package:argus_field/data/update_check.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'harness.dart';

const _latest = 'GET /repos/${AppConfig.releasesRepo}/releases/latest';

AppConfig _published(String version) => AppConfig(
      environment: testConfig.environment,
      apiBase: testConfig.apiBase,
      linkHost: testConfig.linkHost,
      oidcIssuer: '',
      oidcClientId: '',
      oidcRedirect: '',
      appVersion: version,
      distribution: 'github',
    );

http.Response _release(String tag) => http.Response(
    jsonEncode({
      'tag_name': tag,
      'html_url': 'https://github.com/${AppConfig.releasesRepo}/releases/tag/$tag',
      'assets': [
        {'name': 'argus-field-$tag.apk', 'browser_download_url': 'https://github.com/dl/argus-field-$tag.apk'},
      ],
    }),
    200);

void main() {
  test('versions compare as numbers, part by part', () {
    expect(isNewerVersion('1.35.10', '1.35.9'), isTrue);
    expect(isNewerVersion('1.35.9', '1.35.9'), isFalse);
    expect(isNewerVersion('1.35.8', '1.35.9'), isFalse);
    expect(isNewerVersion('1.36', '1.35.9'), isTrue);
  });

  testWidgets('a build published on GitHub offers a newer release, and can be put off', (tester) async {
    final r = await start(tester, config: _published('1.35.8'),
        prepare: (s) => s.routes[_latest] = _release('v1.35.9'));
    expect(find.text('Version 1.35.9 is available.'), findsOneWidget);
    expect(find.byKey(const Key('home-update-download')), findsOneWidget);
    await tester.tap(find.text('Later'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('home-update')), findsNothing);
    expect(r.server.requests.where((q) => q.url.host == 'api.github.com'), hasLength(1));
  });

  testWidgets('nothing is offered when this is the latest', (tester) async {
    await start(tester, config: _published('1.35.9'), prepare: (s) => s.routes[_latest] = _release('v1.35.9'));
    expect(find.byKey(const Key('home-update')), findsNothing);
  });

  testWidgets('a build not from GitHub (Play, a developer) never asks GitHub', (tester) async {
    final r = await start(tester, prepare: (s) => s.routes[_latest] = _release('v9.0.0'));
    expect(find.byKey(const Key('home-update')), findsNothing);
    expect(r.server.requests.where((q) => q.url.host == 'api.github.com'), isEmpty);
  });
}
