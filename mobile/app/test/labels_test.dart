import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('a QR code put on a record shows at once, and the record and its history are read again',
      (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    final historyReads = r.server.requests.where((q) => q.url.path.endsWith('/history')).length;
    final assetReads = r.server.requests.where((q) => q.url.path == '/v1/assets/$ionPumpUid').length;

    await r.tap('label-add');
    await r.type('label-value', 'QR-GUN-0042');
    await r.tap('label-save');

    final sent = r.server.sent('POST', '/v1/assets/$ionPumpUid/labels').single;
    expect(sent['type'], 'qrcode', reason: 'a QR code is what is offered first');
    expect(sent['value'], 'QR-GUN-0042');
    expect(find.text('QR code: QR-GUN-0042'), findsOneWidget);
    expect(r.server.requests.where((q) => q.url.path.endsWith('/history')).length, greaterThan(historyReads));
    expect(r.server.requests.where((q) => q.url.path == '/v1/assets/$ionPumpUid').length, greaterThan(assetReads));

    // Taken off again, after saying what that means.
    final uid = sent['uid'] as String;
    await tester.tap(find.descendant(of: find.byKey(Key('label-$uid')), matching: find.byTooltip('Delete')));
    await tester.pumpAndSettle();
    await r.tap('label-remove-confirm');
    expect(r.server.requests.where((q) => q.method == 'DELETE' && q.url.path.endsWith('/labels/$uid')), hasLength(1));
    expect(find.text('QR code: QR-GUN-0042'), findsNothing);
  });

  testWidgets('a serial is read from the label in front of you', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await r.tap('label-add');
    await tester.tap(find.byKey(const Key('label-type')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Serial number').last);
    await tester.pumpAndSettle();
    await r.type('label-value', 'SN 12345');
    await r.tap('label-save');
    expect(r.server.sent('POST', '/v1/assets/$ionPumpUid/labels').single['type'], 'serial');
  });
}
