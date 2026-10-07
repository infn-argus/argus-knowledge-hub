import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('home shows the cockpit: assigned to me, open tickets, hotspots, reviews and recent activity',
      (tester) async {
    final r = await start(tester);
    r.server.serveOverview = true;
    await r.go('/tickets');
    await r.go('/');

    expect(find.text('ASSIGNED TO ME'), findsOneWidget);
    expect(find.text('1 open ticket'), findsOneWidget);
    expect(find.byKey(const Key('cockpit-asset-$ionPumpUid')), findsWidgets);
    expect(find.text('DOCUMENTS TO REVIEW'), findsOneWidget);
    expect(find.text('RECENT ACTIVITY'), findsOneWidget);

    await r.tap('cockpit-open-tickets');
    expect(find.byKey(const Key('tickets-list')), findsOneWidget);
  });
}
