import 'package:argus_field/domain/capture.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

Future<Running> _settings(WidgetTester tester) async {
  final r = await start(tester);
  await r.tap('nav-menu');
  await r.tap('drawer-settings');
  return r;
}

void main() {
  test('a notification opens what it is about', () {
    expect(const NotificationItem(id: 1, title: 'x', subject: 'document', subjectUid: 'd1').route, '/document/d1');
    expect(const NotificationItem(id: 1, title: 'x', subject: 'asset', subjectUid: 'a1').route, '/asset/a1');
    expect(const NotificationItem(id: 1, title: 'x', issueUid: 't1', subject: 'ticket', subjectUid: 't1').route,
        '/ticket/t1');
    expect(const NotificationItem(id: 1, title: 'x').route, isNull);
  });

  testWidgets('what to hear about is chosen per workspace', (tester) async {
    final r = await _settings(tester);
    await tester.dragUntilVisible(find.byKey(const Key('settings-subscription-$workspaceId')),
        find.byType(Scrollable).first, const Offset(0, -200));
    expect(find.text('Nothing new'), findsWidgets);
    await r.tap('settings-subscription-$workspaceId');
    await r.tap('subscribe-$workspaceId-tickets');
    await r.tap('subscribe-$workspaceId-assets');
    expect(r.server.sent('PUT', '/v1/notifications/subscriptions/$workspaceId').last,
        {'tickets': true, 'documents': false, 'assets': true});
    expect(find.text('New tickets, equipment'), findsOneWidget);
    expect(find.text('Ring'), findsOneWidget, reason: 'every workspace the person can open');
  });

  testWidgets('news on the phone is switched on and off', (tester) async {
    final r = await _settings(tester);
    final phone = find.byKey(const Key('settings-phone-notifications'));
    expect(tester.widget<SwitchListTile>(phone).value, isFalse);
    await r.tap('settings-phone-notifications');
    expect(tester.widget<SwitchListTile>(phone).value, isTrue);
    await r.tap('settings-phone-notifications');
    expect(tester.widget<SwitchListTile>(phone).value, isFalse);
  });
}
