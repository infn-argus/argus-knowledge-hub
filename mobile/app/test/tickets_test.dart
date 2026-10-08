import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('the ticket list shows the open tickets, or all of them, and opens one', (tester) async {
    final r = await start(tester);
    await r.tap('nav-tickets');

    expect(find.text('Pressure spike on gun ion pump'), findsOneWidget);
    expect(find.text('Cooling water leak fixed'), findsNothing, reason: 'closed: not among the open ones');

    await tester.tap(find.text('All'));
    await tester.pumpAndSettle();
    expect(find.text('Cooling water leak fixed'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('tickets-search')), 'leak');
    await tester.pumpAndSettle();
    expect(find.text('Pressure spike on gun ion pump'), findsNothing);

    await tester.enterText(find.byKey(const Key('tickets-search')), '');
    await tester.pumpAndSettle();
    await r.tap('ticket-$ticketUid');
    expect(find.byKey(const Key('ticket-title')), findsOneWidget);
  });

  testWidgets('editing a ticket sends only what was changed, with the version read — never the fields left alone',
      (tester) async {
    final r = await start(tester);
    await r.go('/ticket/$ticketUid');
    await r.tap('ticket-edit');

    await r.type('ticket-edit-title', 'Pressure spike on gun ion pump — HV trips');
    await tester.tap(find.byKey(const Key('ticket-edit-priority')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Urgent').last);
    await tester.pumpAndSettle();
    await r.tap('ticket-edit-save');

    final put = r.server.requests.lastWhere((q) => q.method == 'PUT' && q.url.path == '/v1/issues/$ticketUid');
    expect(put.headers['If-Match'], '"1"');
    final sent = jsonDecode(put.body) as Map;
    // The generated model would also send asset_uid, assignee, labels… as null and clear them.
    expect(sent.keys.toSet(), {'title', 'priority'});
    expect(sent['title'], 'Pressure spike on gun ion pump — HV trips');
    expect(sent['priority'], 'Urgent');
    expect(find.byKey(const Key('ticket-edit-save')), findsNothing, reason: 'saving returns to the ticket');
  });

  testWidgets('saving without a change sends nothing', (tester) async {
    final r = await start(tester);
    await r.go('/ticket/$ticketUid');
    await r.tap('ticket-edit');
    await r.tap('ticket-edit-save');
    expect(r.server.requests.where((q) => q.method == 'PUT'), isEmpty);
  });
}
