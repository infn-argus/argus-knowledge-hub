import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('a new unit starts from a similar one scanned, and keeps its own identifiers and QR code',
      (tester) async {
    final r = await start(tester);
    r.server.labelLookups['QR-PUMP-GUN'] = {
      'kind': 'asset', 'uid': ionPumpUid, 'key': 'SLICE-20463F-IP-0001', 'name': 'Ion pump gun area 2', 'type': 'Ion Pump',
    };
    await r.go('/register?label=SN-NEW-9');
    expect(find.widgetWithText(TextField, 'SN-NEW-9'), findsOneWidget, reason: 'the label that found nothing');

    await r.tap('register-copy');
    await r.type('scan-typed', 'QR-PUMP-GUN');
    await tester.testTextInput.receiveAction(TextInputAction.go);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('register-copied')), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Ion pump gun area 2'), findsOneWidget, reason: 'its name, to edit');
    expect(find.widgetWithText(TextField, 'SN-NEW-9'), findsOneWidget, reason: 'its own serial is not replaced');

    await r.type('register-name', 'Ion pump gun area 3');
    await r.type('register-qr', 'QR-PUMP-GUN-3');
    await r.tap('register-save');

    final created = r.server.sent('POST', '/v1/assets').single;
    expect(created['schema_uid'], 'slice-20463f:argus-object:ion-pump');
    final attrs = created['attributes'] as Map;
    expect(attrs['pumping_speed'], 120.5, reason: 'what is the same is copied');
    expect(attrs['serial'], 'SN-NEW-9');
    final label = r.server.sent('POST', '/v1/assets/${created['uid']}/labels').single;
    expect((label['type'], label['value']), ('qrcode', 'QR-PUMP-GUN-3'));
  });
}
