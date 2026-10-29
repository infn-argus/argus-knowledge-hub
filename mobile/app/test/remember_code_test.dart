import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:argus_field/features/records/resolve_screen.dart' show rememberedKind;

import 'fake_server.dart';
import 'harness.dart';

const _code = 'P/N:2000036233 S/N:40700509';

void main() {
  testWidgets('a unit found by the serial inside a code asks before opening, and remembers the whole code',
      (tester) async {
    final app = await start(tester);
    app.server.labelLookups[_code] = {'kind': 'asset', 'uid': ionPumpUid, 'key': 'SLICE-IP-1', 'name': 'Basler camera',
      'type': 'Camera', 'matched': {'by': 'part', 'part': '40700509', 'code': _code}};
    await app.go('/lookup/${Uri.encodeComponent(_code)}');
    expect(find.textContaining('by “40700509”'), findsOneWidget);
    await app.tap('resolve-remember-open');
    final [label] = app.server.sent('POST', '/v1/assets/$ionPumpUid/labels');
    expect(label['value'], _code);
    expect(label['type'], 'barcode');
  });

  testWidgets('just opening it remembers nothing', (tester) async {
    final app = await start(tester);
    app.server.labelLookups[_code] = {'kind': 'asset', 'uid': ionPumpUid, 'name': 'Basler camera',
      'matched': {'by': 'part', 'part': '40700509', 'code': _code}};
    await app.go('/lookup/${Uri.encodeComponent(_code)}');
    await app.tap('resolve-just-open');
    expect(app.server.sent('POST', '/v1/assets/$ionPumpUid/labels'), isEmpty);
    expect(find.byKey(const Key('resolve-remember-open')), findsNothing);
  });

  testWidgets('an unknown code can be remembered on a unit the person finds', (tester) async {
    final app = await start(tester);
    app.server.labelLookups['something-else'] = {'kind': 'asset', 'uid': ionPumpUid};
    await app.go('/lookup/${Uri.encodeComponent(_code)}');
    await app.tap('resolve-remember');
    await app.type('remember-search', 'GUNSIP');
    await tester.pumpAndSettle();
    await app.tap('remember-on-1bc838cd-4154-4945-8c94-a86e327eba5c');
    final [label] = app.server.sent('POST', '/v1/assets/1bc838cd-4154-4945-8c94-a86e327eba5c/labels');
    expect(label['value'], _code);
  });

  test('a web address is remembered as a QR code, anything else as a barcode', () {
    expect(rememberedKind('https://maker.example/p?sn=1'), 'qrcode');
    expect(rememberedKind(_code), 'barcode');
  });
}
