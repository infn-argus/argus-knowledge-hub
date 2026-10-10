import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('home shows the cockpit: the counts, your tickets, hotspots, knowledge health, states and activity',
      (tester) async {
    final r = await start(tester, prepare: (s) => s.serveOverview = true);

    expect(find.text('YOUR TICKETS'), findsOneWidget);
    expect(find.text('Open tickets'), findsOneWidget);
    expect(find.text('2 in total'), findsOneWidget);
    expect(find.text('Awaiting approval'), findsOneWidget);
    expect(find.byKey(const Key('cockpit-asset-$ionPumpUid')), findsWidgets);
    expect(find.text('KNOWLEDGE HEALTH'), findsOneWidget);
    expect(find.textContaining('waiting for approval'), findsOneWidget);
    expect(find.byKey(const Key('cockpit-by-state')), findsOneWidget);
    expect(find.text('RECENT ACTIVITY'), findsOneWidget);

    await r.tap('cockpit-open-tickets');
    expect(find.byKey(const Key('tickets-list')), findsOneWidget);
  });
}
