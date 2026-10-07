import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fake_server.dart';
import 'harness.dart';

const _vendorCode = 'https://www.pfeiffer-vacuum.com/p/HiPace80?sn=123456';

void main() {
  testWidgets('a manufacturer\'s QR code registered as a label opens the record that carries it', (tester) async {
    final app = await start(tester);
    app.server.routes['GET /v1/links/resolve'] = http.Response(
        jsonEncode({'kind': 'asset', 'uid': positionUid, 'key': 'SLICE-20463F-POS-0001', 'name': 'Gun ion pump',
          'web_path': '/assets/$positionUid'}),
        200,
        headers: {'content-type': 'application/json'});

    await app.go('/lookup/${Uri.encodeComponent(_vendorCode)}');

    final asked = app.server.requests.where((r) => r.url.path == '/v1/links/resolve').last;
    expect(asked.url.queryParameters['path'], '/lookup/${Uri.encodeComponent(_vendorCode)}');
    expect(find.byKey(const Key('resolve-foreign-link')), findsNothing);
  });

  testWidgets('a web link no record carries says whose it is, and is not opened', (tester) async {
    final app = await start(tester);

    await app.go('/lookup/${Uri.encodeComponent(_vendorCode)}');

    expect(find.byKey(const Key('resolve-foreign-link')), findsOneWidget);
    expect(find.textContaining('www.pfeiffer-vacuum.com'), findsWidgets);
    expect(find.byKey(const Key('resolve-register')), findsOneWidget);
  });
}
