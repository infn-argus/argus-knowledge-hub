import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('a record shows what it connects to, grouped by relation, and opens as a graph', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$positionUid');

    // Connections: the two inbound edges the fixture carries, grouped under their relation names. (Its
    // files, comments and history are covered at the data level in repositories_test.dart — fetched by
    // three separate, independently-refreshable calls — and the same scrollable ListView rendering them
    // is already exercised by asset_edit_screen_test.dart.)
    expect(find.text('acts on'), findsOneWidget);
    expect(find.text('installed at'), findsOneWidget);
    expect(find.text('Control Device'), findsOneWidget);

    await r.tap('asset-graph');
    await tester.pumpAndSettle();
    expect(find.text('Relations of GUNSIP01'), findsOneWidget);
    // The centre node and the two neighbours, drawn as the radial graph.
    expect(find.textContaining('GUNSIP01'), findsWidgets);
    expect(find.textContaining('INS-01M3MTM6768A8HE1ZQFE397AR0'), findsOneWidget);
  });

  testWidgets('a reference attribute is shown by the name of what it points at, and opens it', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await tester.drag(find.byKey(const Key('asset-body-list')), const Offset(0, -2000));
    await tester.pumpAndSettle();

    expect(find.text('Instance of'), findsOneWidget);
    expect(find.text('pm-ace2'), findsNothing); // never the bare uid
    expect(find.text('PM-ACE2 · Ace 2 a2A1920-51gmBAS'), findsOneWidget); // the target's name instead

    await tester.tap(find.text('PM-ACE2 · Ace 2 a2A1920-51gmBAS'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('asset-name')), findsOneWidget); // opened the target record
    expect(find.text('Ace 2 a2A1920-51gmBAS'), findsWidgets); // its name, both app bar and body
  });
}
