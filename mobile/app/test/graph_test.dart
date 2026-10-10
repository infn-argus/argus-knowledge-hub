import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('a record in the knowledge graph: connected by relations, and related by meaning', (tester) async {
    final r = await start(tester);
    await r.go('/graph/asset/$ionPumpUid?title=Ion%20pump');
    expect(find.text('Pressure spike on gun ion pump'), findsOneWidget, reason: 'connected');
    expect(find.text('Rossi'), findsNothing, reason: 'people are not walked to from here');
    expect(find.text('DOC-0001 Ion pump replacement'), findsOneWidget, reason: 'related by meaning');
    expect(find.text('0.82'), findsOneWidget);
    expect(r.server.requests.where((q) => q.url.path == '/v1/graph/semantic').single.url.queryParameters,
        {'kind': 'asset', 'uid': ionPumpUid});

    await r.tap('meaning-$documentUid');
    expect(find.textContaining('Replace the ion pump and bake the sector'), findsOneWidget, reason: 'why');

    await r.tap('connected-$ticketUid');
    expect(r.server.requests.where((q) => q.url.path == '/v1/graph').last.url.queryParameters['kind'], 'ticket',
        reason: 'walking on, from the ticket');
  });

  testWidgets('a ticket shows what is about the same thing, read only when opened', (tester) async {
    final r = await start(tester);
    await r.go('/ticket/$ticketUid');
    await tester.dragUntilVisible(
        find.byKey(const Key('related-by-meaning')), find.byType(Scrollable).first, const Offset(0, -300));
    expect(r.server.requests.where((q) => q.url.path == '/v1/graph/semantic'), isEmpty);
    await r.tap('related-by-meaning');
    expect(r.server.requests.where((q) => q.url.path == '/v1/graph/semantic'), hasLength(1));
    expect(find.text('DOC-0001 Ion pump replacement'), findsOneWidget);
  });
}
